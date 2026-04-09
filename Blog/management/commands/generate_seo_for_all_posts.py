from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from Blog.models import Post, Category
from home.models import Rabota
from home.seo_utils import SEOUtils
import logging
import re

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Полная автогенерация SEO мета-тегов для всех объектов на сайте'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно перегенерировать SEO для всех объектов',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
        # --- Часть 1: Статьи ---
        self.stdout.write('--- Action: SEO Articles ---')
        posts = Post.objects.all() if force else Post.objects.filter(Q(meta_title='') | Q(meta_description=''))
        processed_posts = 0
        with transaction.atomic():
            for post in posts:
                try:
                    if not post.meta_title and post.title:
                        post.meta_title = SEOUtils.generate_meta_title(post.title)
                    if not post.meta_description:
                        source = post.description or post.content or ""
                        text_content = re.sub(r'<[^>]+>', '', source)
                        post.meta_description = SEOUtils.generate_meta_description(text_content)
                    post.save(update_fields=['meta_title', 'meta_description', 'meta_keywords'])
                    processed_posts += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'FAIL (Post {post.id}): {e}'))
        self.stdout.write(self.style.SUCCESS(f'OK: {processed_posts} posts'))

        # --- Часть 2: Категории ---
        self.stdout.write('\n--- Action: SEO Categories ---')
        cats = Category.objects.all() if force else Category.objects.filter(Q(meta_title__isnull=True) | Q(meta_title=''))
        processed_cats = 0
        for cat in cats:
            try:
                cat.save() 
                processed_cats += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'FAIL (Cat {cat.id}): {e}'))
        self.stdout.write(self.style.SUCCESS(f'OK: {processed_cats} categories'))

        # --- Часть 3: Портфолио (Работы) ---
        self.stdout.write('\n--- Action: SEO Portfolio (Rabota) ---')
        rabotas = Rabota.objects.all() if force else Rabota.objects.filter(Q(meta_title='') | Q(meta_description=''))
        processed_rabotas = 0
        for r in rabotas:
            try:
                if not r.meta_title:
                    r.meta_title = f"{r.name} | Кейс LukInterLab"
                if not r.meta_description:
                    r.meta_description = SEOUtils.generate_meta_description(r.body or "", 160)
                r.save(update_fields=['meta_title', 'meta_description'])
                processed_rabotas += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'FAIL (Rabota {r.id}): {e}'))
        self.stdout.write(self.style.SUCCESS(f'OK: {processed_rabotas} portfolio items'))

        self.stdout.write(self.style.SUCCESS('\nALL DONE!'))

