"""
Анализ стоимости использования токенов GigaChat
"""
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from typing import Dict, Any, List
import logging

from .models import TokenUsage

logger = logging.getLogger(__name__)


class TokenCostAnalyzer:
    """Анализатор стоимости использования токенов"""
    
    @staticmethod
    def calculate_cost(model: str, tokens: int) -> float:
        """
        Рассчитать стоимость использования токенов для конкретной модели
        
        Args:
            model: Название модели (GigaChat, GigaChat-Pro, GigaChat-Max, GigaChat-Lite и т.д.)
            tokens: Количество токенов
            
        Returns:
            Стоимость в рублях
        """
        rate = TokenUsage.TOKEN_RATES.get(model, 0.000194)
        return tokens * rate
    
    @staticmethod
    def calculate_potential_cost(days: int = 30) -> Dict[str, Any]:
        """
        Рассчитать потенциальную стоимость использования токенов
        если бы использовалась пакетная оплата вместо подписки
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Dict с анализом стоимости
        """
        date_from = timezone.now().date() - timedelta(days=days)
        
        # Получаем статистику по моделям
        stats = TokenUsage.objects.filter(date__gte=date_from).values('model').annotate(
            tokens=Sum('total_tokens'),
            requests=Sum('requests_count'),
        )
        
        total_cost = 0.0
        by_model = []
        
        for stat in stats:
            model = stat['model']
            tokens = stat['tokens'] or 0
            
            # Рассчитываем стоимость по тарифам
            rate = TokenUsage.TOKEN_RATES.get(model, 0.000194)
            cost = tokens * rate
            
            total_cost += cost
            
            by_model.append({
                'model': model,
                'tokens': tokens,
                'cost': cost,
                'rate': rate,
                'requests': stat.get('requests', 0),
            })
        
        # Прогноз на год
        days_in_year = 365
        daily_avg_cost = total_cost / days if days > 0 else 0
        yearly_projection = daily_avg_cost * days_in_year
        
        # Сравнение с пакетными тарифами (PACKAGE_INFO: модель -> список тарифных ступеней)
        package_comparison = []
        for package_name, package_options in TokenUsage.PACKAGE_INFO.items():
            tiers = package_options if isinstance(package_options, list) else (
                [package_options] if isinstance(package_options, dict) else []
            )
            for package_info in tiers:
                if not isinstance(package_info, dict):
                    continue
                price = package_info.get('price') or 0
                tokens_in_pkg = package_info.get('tokens')
                if yearly_projection > 0 and price:
                    packages_needed = yearly_projection / price
                    package_comparison.append({
                        'package': package_name,
                        'tier_tokens': tokens_in_pkg,
                        'yearly_cost': yearly_projection,
                        'package_price': price,
                        'packages_needed': packages_needed,
                        'tokens_in_package': tokens_in_pkg,
                        'savings_if_package': max(0, yearly_projection - price) if packages_needed <= 1 else 0,
                    })
        
        return {
            'period_days': days,
            'total_tokens': sum(s['tokens'] for s in by_model),
            'total_cost': total_cost,
            'daily_avg_cost': daily_avg_cost,
            'yearly_projection': yearly_projection,
            'by_model': by_model,
            'package_comparison': package_comparison,
        }
    
    @staticmethod
    def get_cost_efficiency_report(days: int = 30) -> Dict[str, Any]:
        """
        Получить отчет об эффективности использования токенов
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Dict с отчетом
        """
        analysis = TokenCostAnalyzer.calculate_potential_cost(days)
        
        # Находим самую используемую модель
        if analysis['by_model']:
            most_used = max(analysis['by_model'], key=lambda x: x['tokens'])
        else:
            most_used = None
        
        # Рекомендации
        recommendations = []
        
        if analysis['yearly_projection'] > 0:
            # Если годовая стоимость высока, рекомендуем пакет
            if analysis['yearly_projection'] > 2000:
                recommendations.append({
                    'type': 'package',
                    'message': f"Рекомендуется рассмотреть покупку пакета токенов. "
                               f"Годовая стоимость: {analysis['yearly_projection']:.2f} ₽",
                    'priority': 'high',
                })
            
            # Если используется много токенов Lite, рекомендуем пакет Lite
            lite_usage = next(
                (m for m in analysis['by_model'] if 'Lite' in m['model']),
                None
            )
            if lite_usage and lite_usage['tokens'] > 1_000_000:
                recommendations.append({
                    'type': 'lite_package',
                    'message': f"Использовано {lite_usage['tokens']:,} токенов Lite. "
                               f"Рекомендуется пакет Lite (30M токенов за 5,820 ₽)",
                    'priority': 'medium',
                })
        
        return {
            'analysis': analysis,
            'most_used_model': most_used,
            'recommendations': recommendations,
            'summary': {
                'total_tokens': analysis['total_tokens'],
                'total_cost': analysis['total_cost'],
                'yearly_projection': analysis['yearly_projection'],
                'cost_per_token_avg': (
                    analysis['total_cost'] / analysis['total_tokens']
                    if analysis['total_tokens'] > 0 else 0
                ),
            },
        }
    
    @staticmethod
    def compare_subscription_vs_packages(days: int = 30) -> Dict[str, Any]:
        """
        Сравнить стоимость подписки и пакетной оплаты
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Dict с сравнением
        """
        analysis = TokenCostAnalyzer.calculate_potential_cost(days)
        
        # Стоимость подписки (если бы была)
        # Предполагаем, что подписка стоит примерно как пакет Pro
        subscription_cost_per_year = 1500  # Примерная стоимость
        
        return {
            'subscription_cost_per_year': subscription_cost_per_year,
            'package_cost_per_year': analysis['yearly_projection'],
            'savings_with_subscription': max(0, analysis['yearly_projection'] - subscription_cost_per_year),
            'savings_with_packages': max(0, subscription_cost_per_year - analysis['yearly_projection']),
            'recommendation': (
                'subscription' if analysis['yearly_projection'] > subscription_cost_per_year
                else 'packages'
            ),
            'analysis': analysis,
        }

