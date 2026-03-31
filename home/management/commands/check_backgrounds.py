from django.core.management.base import BaseCommand
from home.models import SectionBackground


class Command(BaseCommand):
    help = 'Проверка фонов секций'

    def handle(self, *args, **options):
        self.stdout.write('Проверка фонов секций...')
        
        backgrounds = SectionBackground.objects.all()
        
        if not backgrounds.exists():
            self.stdout.write(self.style.ERROR('Фоны секций не найдены!'))
            return
        
        for bg in backgrounds:
            self.stdout.write(f'Секция: {bg.section}')
            self.stdout.write(f'  Тип: {bg.background_type}')
            self.stdout.write(f'  Активен: {bg.is_active}')
            self.stdout.write(f'  Стиль фона: {bg.get_background_style()}')
            self.stdout.write(f'  Стиль наложения: {bg.get_overlay_style()}')
            self.stdout.write(f'  URL видео: {bg.get_video_url()}')
            self.stdout.write('---')
        
        self.stdout.write(self.style.SUCCESS(f'Найдено {backgrounds.count()} фонов секций')) 