"""
Команда для очистки кэша портфолио
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from home.models import Rabota


class Command(BaseCommand):
    help = 'Очищает кэш портфолио и показывает статистику работ'

    def handle(self, *args, **options):
        self.stdout.write('Очистка кэша портфолио...')
        
        # Очищаем кэш
        cache.delete('home_rabotas')
        cache.delete('home_page_data')
        self.stdout.write(self.style.SUCCESS('✓ Кэш очищен'))
        
        # Показываем статистику
        self.stdout.write('\nСтатистика работ:')
        
        total = Rabota.objects.count()
        completed = Rabota.objects.filter(status='completed').count()
        
        self.stdout.write(f'  Всего работ: {total}')
        self.stdout.write(f'  Завершенных (отображаются): {completed}')
        
        # По категориям
        categories = ['website', 'bot', 'app', 'shop', 'other']
        for cat in categories:
            count = Rabota.objects.filter(status='completed', category=cat).count()
            cat_name = dict(Rabota.CATEGORY_CHOICES).get(cat, cat)
            self.stdout.write(f'    {cat_name}: {count}')
        
        # Работы без изображений
        no_image = Rabota.objects.filter(status='completed', image='').count()
        if no_image > 0:
            self.stdout.write(self.style.WARNING(f'\n⚠ Работ без изображений: {no_image}'))
        
        self.stdout.write(self.style.SUCCESS('\nГотово! Обновите страницу для применения изменений.'))

