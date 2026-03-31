"""
Management команда для ручного запуска генерации одной тестовой статьи
"""
import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import OperationalError
from Assistant.models import AISchedule, PromptTemplate
from Assistant.article_generator import ArticleGeneratorService
from Blog.models import Category

User = get_user_model()


class Command(BaseCommand):
    help = 'Ручной запуск генерации одной тестовой статьи'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schedule-id',
            type=int,
            help='ID расписания для использования (если не указано, будет использовано первое активное)'
        )

    def handle(self, *args, **options):
        self.stdout.write('Запуск генерации тестовой статьи...')
        
        # Получаем расписание
        schedule_id = options.get('schedule_id')
        if schedule_id:
            try:
                schedule = AISchedule.objects.get(id=schedule_id, is_active=True)
            except AISchedule.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'[ERROR] Расписание с ID {schedule_id} не найдено или неактивно.'
                ))
                return
        else:
            schedule = AISchedule.objects.filter(is_active=True).first()
            if not schedule:
                self.stdout.write(self.style.WARNING(
                    '[WARNING] Не найдено активного расписания. Создайте его в админ-панели или через команду setup_autoposting_schedule.'
                ))
                return
        
        self.stdout.write(f'[INFO] Используется расписание: {schedule.name}')
        
        # Проверяем наличие шаблона промпта
        if not schedule.prompt_template:
            self.stdout.write(self.style.ERROR(
                '[ERROR] У расписания не указан шаблон промпта.'
            ))
            return
        
        # Проверяем наличие категорий
        categories = Category.objects.filter(activ=True)
        if not categories.exists():
            self.stdout.write(self.style.WARNING(
                '[WARNING] Не найдено активных категорий.'
            ))
        
        # Создаем сервис генерации
        try:
            generator = ArticleGeneratorService(schedule)
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'[ERROR] Ошибка создания сервиса генерации: {str(e)}'
            ))
            return
        
        # Генерируем статью
        self.stdout.write('[START] Начало генерации статьи...')
        start_time = time.time()
        
        try:
            post = generator.generate_article()
            
            if post:
                elapsed_time = time.time() - start_time
                self.stdout.write(self.style.SUCCESS(
                    f'\n[OK] Статья успешно сгенерирована!'
                    f'\n   ID: {post.id}'
                    f'\n   Заголовок: {post.title}'
                    f'\n   Категория: {post.category.title if post.category else "Нет"}'
                    f'\n   Автор: {post.author.username}'
                    f'\n   Время генерации: {elapsed_time:.2f} сек'
                    f'\n   URL: {post.get_absolute_url() if hasattr(post, "get_absolute_url") else "N/A"}'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    '[ERROR] Не удалось сгенерировать статью. Проверьте логи.'
                ))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'[ERROR] Ошибка генерации статьи: {str(e)}'
            ))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))

