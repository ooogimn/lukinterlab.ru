from django.core.management.base import BaseCommand
from home.models import SectionBackground


class Command(BaseCommand):
    help = 'Создание фонов секций для главной страницы'

    def handle(self, *args, **options):
        self.stdout.write('Создание фонов секций...')
        
        # Создаем фоны для всех секций
        backgrounds_data = [
            {
                'section': 'home',
                'background_type': 'gradient',
                'gradient_start': '#eff6ff',
                'gradient_end': '#e0e7ff',
                'gradient_direction': 'to-br',
                'overlay_opacity': 0,
                'is_active': True
            },
            {
                'section': 'about',
                'background_type': 'image',
                'overlay_opacity': 0,
                'is_active': True
            },
            {
                'section': 'resume',
                'background_type': 'gradient',
                'gradient_start': '#f9fafb',
                'gradient_end': '#f3f4f6',
                'gradient_direction': 'to-br',
                'overlay_opacity': 0,
                'is_active': True
            },
            {
                'section': 'portfolio',
                'background_type': 'image',
                'overlay_opacity': 0,
                'is_active': True
            },
            {
                'section': 'testimonials',
                'background_type': 'gradient',
                'gradient_start': '#f9fafb',
                'gradient_end': '#f3f4f6',
                'gradient_direction': 'to-br',
                'overlay_opacity': 0,
                'is_active': True
            },
            {
                'section': 'blog',
                'background_type': 'image',
                'overlay_opacity': 0,
                'is_active': True
            },
            {
                'section': 'contact',
                'background_type': 'image',
                'overlay_opacity': 0,
                'is_active': True
            }
        ]
        
        created_count = 0
        for bg_data in backgrounds_data:
            background, created = SectionBackground.objects.get_or_create(
                section=bg_data['section'],
                defaults=bg_data
            )
            if created:
                created_count += 1
                self.stdout.write(f'Создан фон для секции: {bg_data["section"]}')
            else:
                self.stdout.write(f'Фон для секции {bg_data["section"]} уже существует')
        
        self.stdout.write(
            self.style.SUCCESS(f'Успешно создано {created_count} фонов секций!')
        ) 