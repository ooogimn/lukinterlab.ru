"""
Management команда для исправления всех статей без slug
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from Blog.models import Post


class Command(BaseCommand):
    help = 'Исправление всех статей без slug - генерирует slug из заголовка'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет исправлено без сохранения'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        # Находим все статьи без slug
        posts_without_slug = Post.objects.filter(slug='') | Post.objects.filter(slug__isnull=True)
        
        count = posts_without_slug.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('[OK] Все статьи имеют slug'))
            return
        
        self.stdout.write(f'[INFO] Найдено статей без slug: {count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Режим проверки (без сохранения)'))
        else:
            self.stdout.write('[INFO] Начинаю исправление...')
        
        fixed_count = 0
        error_count = 0
        
        for post in posts_without_slug:
            try:
                # Генерируем slug из заголовка
                base_slug = slugify(post.title)
                
                # Если slug пустой, используем дефолтный с ID
                if not base_slug:
                    base_slug = f'post-{post.id}'
                
                # Проверяем уникальность (с учетом unique_for_date)
                original_slug = base_slug
                counter = 1
                
                # Используем дату создания статьи
                created_date = post.created.date() if post.created else timezone.now().date()
                
                # Проверяем уникальность
                while Post.objects.filter(
                    slug=base_slug,
                    created__date=created_date
                ).exclude(pk=post.pk).exists():
                    base_slug = f"{original_slug}-{counter}"
                    counter += 1
                    # Защита от бесконечного цикла
                    if counter > 1000:
                        base_slug = f"{original_slug}-{post.id}-{timezone.now().timestamp()}"
                        break
                
                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] ID: {post.id}, Title: {post.title[:50]}, Slug: {base_slug}')
                else:
                    # Сохраняем slug
                    post.slug = base_slug
                    # Обновляем без триггера сигналов (чтобы избежать лишних операций)
                    Post.objects.filter(pk=post.pk).update(slug=base_slug)
                    self.stdout.write(self.style.SUCCESS(
                        f'  [OK] ID: {post.id}, Title: {post.title[:50]}, Slug: {base_slug}'
                    ))
                    fixed_count += 1
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f'  [ERROR] ID: {post.id}, Title: {post.title[:50]}, Error: {str(e)}'
                ))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY-RUN] Проверка завершена. Найдено статей для исправления: {count}'
                f'\nЗапустите без --dry-run для применения изменений.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n[OK] Исправление завершено!'
                f'\n   Исправлено: {fixed_count}'
                f'\n   Ошибок: {error_count}'
                f'\n   Всего: {count}'
            ))

