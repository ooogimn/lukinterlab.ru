from django.core.management.base import BaseCommand
from django.db import transaction
from home.models import SEOModel
from home.seo_utils import SEOUtils
from Blog.models import Post, Category
from home.models import Otziv, Rabota


class Command(BaseCommand):
    help = 'Автоматическая SEO оптимизация сайта'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить все SEO записи',
        )

    def handle(self, *args, **options):
        self.stdout.write('🚀 Начинаем SEO оптимизацию...')
        
        with transaction.atomic():
            # Создаем базовые SEO записи для статических страниц
            self.create_static_pages_seo()
            
            # Оптимизируем SEO для постов блога
            self.optimize_blog_posts_seo()
            
            # Оптимизируем SEO для отзывов
            self.optimize_otzivs_seo()
            
            # Оптимизируем SEO для работ
            self.optimize_rabotas_seo()
        
        self.stdout.write(
            self.style.SUCCESS('✅ SEO оптимизация завершена успешно!')
        )

    def create_static_pages_seo(self):
        """Создание SEO для статических страниц"""
        static_pages = [
            {
                'page_url': '/',
                'title': 'LukInterLab - IT решения под ключ | Разработка сайтов, ботов, приложений',
                'description': 'Создаем сайты, боты, приложения и интернет-магазины под ключ. Современные IT решения для вашего бизнеса в Москве.',
                'keywords': 'разработка сайтов, телеграм боты, мобильные приложения, интернет магазин, IT услуги, Москва',
                'h1': 'LukInterLab - IT решения под ключ'
            },
            {
                'page_url': '/otziv/',
                'title': 'Отзывы клиентов LukInterLab | Реальные отзывы о разработке',
                'description': 'Читайте отзывы наших клиентов о разработке сайтов, ботов и приложений. Реальные проекты и довольные заказчики.',
                'keywords': 'отзывы клиентов, отзывы о разработке, отзывы LukInterLab, проекты',
                'h1': 'Отзывы наших клиентов'
            },
            {
                'page_url': '/otzivs/create/',
                'title': 'Оставить отзыв | LukInterLab',
                'description': 'Оставьте отзыв о нашей работе. Ваше мнение важно для нас и поможет другим клиентам.',
                'keywords': 'оставить отзыв, отзыв о работе, отзыв о разработке',
                'h1': 'Оставить отзыв'
            },
        ]
        
        for page_data in static_pages:
            seo, created = SEOModel.objects.get_or_create(
                page_url=page_data['page_url'],
                defaults=page_data
            )
            
            if created:
                self.stdout.write(f'✅ Создана SEO запись для {page_data["page_url"]}')
            elif options.get('force'):
                for key, value in page_data.items():
                    setattr(seo, key, value)
                seo.save()
                self.stdout.write(f'🔄 Обновлена SEO запись для {page_data["page_url"]}')

    def optimize_blog_posts_seo(self):
        """Оптимизация SEO для постов блога"""
        posts = Post.objects.filter(status='published')
        
        for post in posts:
            # Генерируем SEO данные
            title = SEOUtils.generate_meta_title(
                f"{post.title} | Блог LukInterLab"
            )
            description = SEOUtils.generate_meta_description(
                post.content[:200] + "..." if len(post.content) > 200 else post.content
            )
            keywords = ', '.join(SEOUtils.extract_keywords(post.content, 5))
            
            # Создаем или обновляем SEO запись
            seo, created = SEOModel.objects.get_or_create(
                page_url=post.get_absolute_url(),
                defaults={
                    'title': title,
                    'description': description,
                    'keywords': keywords,
                    'h1': post.title
                }
            )
            
            if created:
                self.stdout.write(f'✅ Создана SEO запись для поста: {post.title}')
            elif options.get('force'):
                seo.title = title
                seo.description = description
                seo.keywords = keywords
                seo.h1 = post.title
                seo.save()
                self.stdout.write(f'🔄 Обновлена SEO запись для поста: {post.title}')

    def optimize_otzivs_seo(self):
        """Оптимизация SEO для отзывов"""
        otzivs = Otziv.objects.filter(active=True)
        
        for otziv in otzivs:
            title = SEOUtils.generate_meta_title(
                f"Отзыв от {otziv.name} | LukInterLab"
            )
            description = SEOUtils.generate_meta_description(
                f"Отзыв клиента {otziv.name} о работе LukInterLab. {otziv.body[:100]}..."
            )
            
            seo, created = SEOModel.objects.get_or_create(
                page_url=otziv.get_absolute_url(),
                defaults={
                    'title': title,
                    'description': description,
                    'keywords': f'отзыв, {otziv.name}, LukInterLab',
                    'h1': f'Отзыв от {otziv.name}'
                }
            )
            
            if created:
                self.stdout.write(f'✅ Создана SEO запись для отзыва: {otziv.name}')

    def optimize_rabotas_seo(self):
        """Оптимизация SEO для работ"""
        rabotas = Rabota.objects.filter(status='completed')
        
        for rabota in rabotas:
            title = SEOUtils.generate_meta_title(
                f"Проект {rabota.name} | Портфолио LukInterLab"
            )
            description = SEOUtils.generate_meta_description(
                f"Проект {rabota.name} - {rabota.body[:150]}..."
            )
            
            seo, created = SEOModel.objects.get_or_create(
                page_url=rabota.get_absolute_url(),
                defaults={
                    'title': title,
                    'description': description,
                    'keywords': f'проект, {rabota.name}, портфолио, LukInterLab',
                    'h1': f'Проект: {rabota.name}'
                }
            )
            
            if created:
                self.stdout.write(f'✅ Создана SEO запись для проекта: {rabota.name}') 