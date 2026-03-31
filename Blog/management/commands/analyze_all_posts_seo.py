from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Avg
from Blog.models import Post
from Moderation.services import SEOService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Массовый SEO анализ всех опубликованных статей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно переанализировать все статьи, даже если уже есть SEO score',
        )
        parser.add_argument(
            '--min-score',
            type=int,
            default=0,
            help='Минимальный SEO score для отображения в отчете (по умолчанию 0)',
        )

    def handle(self, *args, **options):
        self.stdout.write('🚀 Начинаем массовый SEO анализ статей...')
        
        force = options.get('force', False)
        min_score = options.get('min_score', 0)
        
        # Получаем все опубликованные статьи
        posts = Post.objects.filter(status='published')
        
        if not force:
            # Если не force, анализируем только статьи без SEO score или с score = 0
            posts = posts.filter(seo_score=0)
        
        total_posts = posts.count()
        self.stdout.write(f'📊 Найдено статей для анализа: {total_posts}')
        
        if total_posts == 0:
            self.stdout.write(self.style.WARNING('⚠️ Нет статей для анализа'))
            return
        
        seo_service = SEOService()
        analyzed_count = 0
        low_score_posts = []
        high_score_posts = []
        
        with transaction.atomic():
            for post in posts:
                try:
                    # Анализируем статью
                    analysis_result = seo_service.analyze_post(post)
                    score = analysis_result['score']
                    
                    # Обновляем SEO score в статье
                    post.seo_score = score
                    post.save(update_fields=['seo_score'])
                    
                    analyzed_count += 1
                    
                    # Собираем статистику
                    if score < 50:
                        low_score_posts.append({
                            'title': post.title,
                            'score': score,
                            'url': post.get_absolute_url(),
                            'recommendations': analysis_result.get('data', {}).get('recommendations', [])
                        })
                    elif score >= 80:
                        high_score_posts.append({
                            'title': post.title,
                            'score': score,
                            'url': post.get_absolute_url()
                        })
                    
                    if analyzed_count % 10 == 0:
                        self.stdout.write(f'✅ Проанализировано: {analyzed_count}/{total_posts}')
                        
                except Exception as e:
                    logger.error(f"Ошибка при анализе статьи {post.id}: {str(e)}", exc_info=True)
                    self.stdout.write(
                        self.style.ERROR(f'❌ Ошибка при анализе статьи "{post.title}": {str(e)}')
                    )
        
        # Выводим отчет
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Анализ завершен! Проанализировано статей: {analyzed_count}'))
        self.stdout.write('')
        
        # Статистика по score
        avg_score = Post.objects.filter(status='published').aggregate(
            avg_score=Avg('seo_score')
        )['avg_score'] or 0
        
        self.stdout.write(f'📊 Средний SEO score: {avg_score:.1f}/100')
        self.stdout.write('')
        
        # Статьи с высоким score
        if high_score_posts:
            self.stdout.write(self.style.SUCCESS(f'🌟 Статьи с высоким SEO score (≥80): {len(high_score_posts)}'))
            for post_info in high_score_posts[:5]:  # Показываем топ-5
                self.stdout.write(f'   • {post_info["title"]} - Score: {post_info["score"]}')
            self.stdout.write('')
        
        # Статьи с низким score
        if low_score_posts:
            self.stdout.write(self.style.WARNING(f'⚠️ Статьи с низким SEO score (<50): {len(low_score_posts)}'))
            for post_info in low_score_posts[:10]:  # Показываем топ-10 проблемных
                self.stdout.write(f'   • {post_info["title"]} - Score: {post_info["score"]}')
                self.stdout.write(f'     URL: {post_info["url"]}')
            self.stdout.write('')
        
        # Рекомендации
        if low_score_posts:
            self.stdout.write('💡 Рекомендации по улучшению:')
            self.stdout.write('   1. Проверьте наличие meta_title и meta_description')
            self.stdout.write('   2. Убедитесь, что статьи содержат достаточно контента (минимум 300 слов)')
            self.stdout.write('   3. Добавьте изображения к статьям')
            self.stdout.write('   4. Используйте структурированные заголовки (H2, H3)')
            self.stdout.write('   5. Добавьте теги к статьям (рекомендуется 3-5 тегов)')
            self.stdout.write('')

