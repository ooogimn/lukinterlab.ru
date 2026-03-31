"""
Management команда для очистки кэша
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Очистка всего кэша'

    def handle(self, *args, **options):
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS('[OK] Кэш полностью очищен'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[ERROR] Ошибка очистки кэша: {str(e)}'))

