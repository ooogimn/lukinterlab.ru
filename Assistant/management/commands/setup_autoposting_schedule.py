"""
Management команда для настройки расписания автопостинга статей
Настройка: каждые 10-20 минут по 1 статье, всего 10 статей в день
"""
import time
import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import OperationalError
from django_q.models import Schedule
from Assistant.models import AISchedule, PromptTemplate
from Blog.models import Category

User = get_user_model()


class Command(BaseCommand):
    help = 'Настройка расписания автопостинга: каждые 10-20 минут по 1 статье, всего 10 статей в день'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-hour',
            type=int,
            default=8,
            help='Час начала автопостинга (по умолчанию 8)'
        )
        parser.add_argument(
            '--end-hour',
            type=int,
            default=22,
            help='Час окончания автопостинга (по умолчанию 22)'
        )
        parser.add_argument(
            '--total-articles',
            type=int,
            default=10,
            help='Всего статей в день (по умолчанию 10)'
        )

    def handle(self, *args, **options):
        self.stdout.write('Настройка расписания автопостинга...')
        
        start_hour = options.get('start_hour', 8)
        end_hour = options.get('end_hour', 22)
        total_articles = options.get('total_articles', 10)
        
        # Проверяем наличие шаблона промпта
        prompt_template = PromptTemplate.objects.filter(is_active=True).first()
        if not prompt_template:
            self.stdout.write(self.style.WARNING(
                '[WARNING] Не найден активный шаблон промпта. Создайте его в админ-панели сначала.'
            ))
            return
        
        # Проверяем наличие категорий
        categories = Category.objects.filter(activ=True)
        if not categories.exists():
            self.stdout.write(self.style.WARNING(
                '[WARNING] Не найдено активных категорий. Создайте их в админ-панели сначала.'
            ))
            return
        
        # Получаем или создаем расписание
        schedule_name = f'Автопостинг статей ({total_articles} статей в день, каждые 10-20 мин)'
        schedule, created = AISchedule.objects.get_or_create(
            name=schedule_name,
            defaults={
                'prompt_template': prompt_template,
                'frequency': 'custom',
                'cron_expression': '',  # Будет заполнено отдельными расписаниями Django-Q
                'articles_per_run': 1,  # Каждый запуск генерирует 1 статью
                'is_active': True,
                'text_model': 'GigaChat',
                'image_model': 'GigaChat-Pro',
                'use_image_generation': False,  # Можно включить если нужно
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'[OK] Создано расписание: {schedule.name}'))
        else:
            self.stdout.write(f'[INFO] Расписание уже существует: {schedule.name}')
            # Обновляем параметры если расписание уже существует
            schedule.articles_per_run = 1
            schedule.save(update_fields=['articles_per_run'])
        
        # Вычисляем время запуска для статей в день
        # Каждый запуск происходит с интервалом 10-20 минут
        total_hours = end_hour - start_hour
        if total_hours <= 0:
            self.stdout.write(self.style.ERROR(
                '[ERROR] Конечный час должен быть больше начального.'
            ))
            return
        
        # Создаем расписание: начинаем с start_hour:00, затем каждые 10-20 минут (случайно)
        schedule_times = []
        current_minute = 0
        current_hour = start_hour
        
        # Первый запуск в начале дня
        schedule_times.append((current_minute, current_hour))
        
        # Генерируем остальные запуски с интервалом 10-20 минут
        for i in range(total_articles - 1):
            # Интервал между запусками: случайное значение от 10 до 20 минут
            interval_minutes = random.randint(10, 20)
            
            # Добавляем интервал к текущему времени
            current_minute += interval_minutes
            
            # Если минут больше 60, переходим на следующий час
            if current_minute >= 60:
                current_hour += current_minute // 60
                current_minute = current_minute % 60
            
            # Проверяем, не вышли ли за пределы рабочего времени
            if current_hour >= end_hour:
                # Если вышли за пределы, перераспределяем оставшиеся статьи
                # равномерно в оставшееся время
                remaining_articles = total_articles - len(schedule_times)
                if remaining_articles > 0:
                    # Распределяем оставшиеся статьи равномерно в период start_hour - end_hour
                    total_minutes_available = (end_hour - start_hour) * 60
                    # Используем только время, которое еще не занято
                    used_minutes = len(schedule_times) * 15  # Средний интервал
                    available_minutes = total_minutes_available - used_minutes
                    
                    if available_minutes > 0 and remaining_articles > 0:
                        minutes_per_article = available_minutes // (remaining_articles + 1)
                        
                        # Начинаем с последнего запланированного времени
                        last_scheduled_time = schedule_times[-1]
                        last_hour, last_minute = last_scheduled_time[1], last_scheduled_time[0]
                        last_total_minutes = (last_hour - start_hour) * 60 + last_minute
                        
                        for j in range(remaining_articles):
                            next_total_minutes = last_total_minutes + minutes_per_article * (j + 1)
                            next_hour = start_hour + (next_total_minutes // 60)
                            next_minute = next_total_minutes % 60
                            
                            if next_hour < end_hour:
                                schedule_times.append((next_minute, next_hour))
                            else:
                                break
                break
            
            schedule_times.append((current_minute, current_hour))
        
        # Удаляем дубликаты
        unique_times = []
        seen = set()
        for minute, hour in schedule_times:
            if (minute, hour) not in seen:
                unique_times.append((minute, hour))
                seen.add((minute, hour))
        schedule_times = unique_times
        
        # Если все еще не набрали нужное количество, добавляем равномерно
        if len(schedule_times) < total_articles:
            # Распределяем равномерно все статьи по всему дню
            total_minutes_available = (end_hour - start_hour) * 60
            minutes_per_article = total_minutes_available // total_articles
            
            schedule_times = []
            seen = set()
            
            for i in range(total_articles):
                # Базовое время
                base_minutes = i * minutes_per_article
                # Добавляем случайную вариацию ±3 минуты для более естественного распределения
                variation = random.randint(-3, 3)
                article_minutes = max(0, min(base_minutes + variation, total_minutes_available - 1))
                
                article_hour = start_hour + (article_minutes // 60)
                article_minute = article_minutes % 60
                
                # Проверяем, что не вышли за пределы и нет дубликата
                if article_hour < end_hour and (article_minute, article_hour) not in seen:
                    schedule_times.append((article_minute, article_hour))
                    seen.add((article_minute, article_hour))
        
        # Ограничиваем количество времен до total_articles (на случай если их больше)
        schedule_times = schedule_times[:total_articles]
        
        # Сортируем по времени
        schedule_times.sort(key=lambda x: (x[1], x[0]))
        
        self.stdout.write(f'[INFO] Создается {len(schedule_times)} расписаний Django-Q:')
        for minute, hour in schedule_times:
            self.stdout.write(f'  - {hour:02d}:{minute:02d}')
        
        # Создаем расписания Django-Q
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for idx, (minute, hour) in enumerate(schedule_times):
            cron_expr = f'{minute} {hour} * * *'
            schedule_name_q = f'ai_autoposting_{hour:02d}{minute:02d}'
            
            # Повторные попытки при блокировке базы данных
            max_retries = 10
            retry_delay = 0.5
            success = False
            
            for attempt in range(max_retries):
                try:
                    q_schedule, q_created = Schedule.objects.update_or_create(
                        name=schedule_name_q,
                        defaults={
                            'func': 'Assistant.tasks.run_schedule_task',
                            'schedule_type': Schedule.CRON,
                            'cron': cron_expr,
                            'args': str(schedule.id),
                            'repeats': -1,  # Бесконечное повторение
                        }
                    )
                    
                    if q_created:
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'  [OK] Создано расписание Django-Q: {hour:02d}:{minute:02d}'
                        ))
                    else:
                        updated_count += 1
                        self.stdout.write(f'  [INFO] Обновлено расписание Django-Q: {hour:02d}:{minute:02d}')
                    
                    success = True
                    break
                    
                except OperationalError as e:
                    if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                        if attempt == 0:
                            self.stdout.write(f'  [WARNING] База данных заблокирована, ожидание...')
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 3)
                    else:
                        error_count += 1
                        self.stdout.write(self.style.ERROR(
                            f'  [ERROR] Не удалось создать расписание {hour:02d}:{minute:02d}: {str(e)}'
                        ))
                        break
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'  [ERROR] Ошибка при создании расписания {hour:02d}:{minute:02d}: {str(e)}'
                    ))
                    break
            
            if not success:
                error_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] Настройка завершена!'
            f'\n   Создано расписаний: {created_count}'
            f'\n   Обновлено расписаний: {updated_count}'
            f'\n   Ошибок: {error_count}'
            f'\n   Всего: {len(schedule_times)} расписаний'
            f'\n   Статей в день: {total_articles}'
            f'\n   Интервал: 10-20 минут между запусками'
        ))
        
        if error_count > 0:
            self.stdout.write(self.style.WARNING(
                f'\n[WARNING] Некоторые расписания не удалось создать из-за блокировки базы данных.'
                f'\n   Попробуйте запустить команду еще раз или временно остановите воркер Django-Q.'
            ))
        
        self.stdout.write(self.style.WARNING(
            '\n[WARNING] Не забудьте запустить Django-Q worker:'
            '\n   python manage.py qcluster'
        ))

        from Assistant.tasks import setup_schedules

        setup_schedules()
        self.stdout.write(
            self.style.SUCCESS(
                '[OK] Канонические расписания django-q (ai_schedule_*) синхронизированы; легаси ai_autoposting_* удалены.'
            )
        )
