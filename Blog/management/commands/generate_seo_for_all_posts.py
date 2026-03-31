from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from Blog.models import Post
from home.seo_utils import SEOUtils
import logging
import re

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Автогенерация SEO мета-тегов для всех существующих статей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно перегенерировать SEO для всех статей',
        )

    def handle(self, *args, **options):
        self.stdout.write('🚀 Начинаем автогенерацию SEO мета-тегов...')
        
        force = options.get('force', False)
        
        # Получаем все статьи
        if force:
            posts = Post.objects.all()
        else:
            # Только статьи без SEO мета-тегов
            posts = Post.objects.filter(
                Q(meta_title='') | Q(meta_description='')
            )
        
        total_posts = posts.count()
        self.stdout.write(f'📊 Найдено статей для обработки: {total_posts}')
        
        if total_posts == 0:
            self.stdout.write(self.style.SUCCESS('✅ Все статьи уже имеют SEO мета-теги'))
            return
        
        processed_count = 0
        
        with transaction.atomic():
            for post in posts:
                try:
                    # Генерация meta_title если не указан
                    if not post.meta_title and post.title:
                        post.meta_title = SEOUtils.generate_meta_title(post.title)
                    
                    # Генерация meta_description если не указан
                    if not post.meta_description:
                        if post.description:
                            post.meta_description = SEOUtils.generate_meta_description(post.description)
                        elif post.content:
                            text_content = re.sub(r'<[^>]+>', '', post.content)
                            words = text_content.split()[:25]
                            description_text = ' '.join(words)
                            post.meta_description = SEOUtils.generate_meta_description(description_text)
                    
                    # Генерация meta_keywords если не указаны
                    if not post.meta_keywords:
                        keywords_list = []
                        
                        # Добавляем теги
                        if post.tags.exists():
                            keywords_list.extend([tag.name for tag in post.tags.all()])
                        
                        # Извлекаем ключевые слова из контента
                        if post.content:
                            content_keywords = SEOUtils.extract_keywords(post.content, max_keywords=5)
                            keywords_list.extend(content_keywords)
                        
                        # Убираем дубликаты
                        unique_keywords = list(dict.fromkeys(keywords_list))[:10]
                        post.meta_keywords = ', '.join(unique_keywords)
                    
                    # Генерация focus_keyword если не указан
                    if not post.focus_keyword and post.title:
                        words = post.title.split()
                        stop_words = {'как', 'что', 'для', 'при', 'без', 'под', 'над', 'из', 'от', 'до', 'по', 'со', 'во'}
                        focus_words = [w.lower() for w in words if w.lower() not in stop_words and len(w) > 3]
                        if focus_words:
                            post.focus_keyword = focus_words[0]
                        else:
                            post.focus_keyword = words[0] if words else ''
                    
                    post.save(update_fields=['meta_title', 'meta_description', 'meta_keywords', 'focus_keyword'])
                    processed_count += 1
                    
                    if processed_count % 10 == 0:
                        self.stdout.write(f'✅ Обработано: {processed_count}/{total_posts}')
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке статьи {post.id}: {str(e)}", exc_info=True)
                    self.stdout.write(
                        self.style.ERROR(f'❌ Ошибка при обработке статьи "{post.title}": {str(e)}')
                    )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Обработка завершена! Обработано статей: {processed_count}'))

