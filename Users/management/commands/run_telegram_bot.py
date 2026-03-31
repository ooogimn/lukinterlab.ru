from django.core.management.base import BaseCommand
from Users.telegram_bot import run_bot

class Command(BaseCommand):
    help = 'Запускает Telegram-бота для регистрации пользователя'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Запуск Telegram-бота...'))
        run_bot() 