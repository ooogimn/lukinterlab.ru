import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from django.conf import settings

from Users.models import TelegramUser


# Настройка ведения журнала
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправьте сообщение при выполнении команды /пуск."""
    user = update.effective_user
    await update.message.reply_text(
        f'Привет, {user.first_name}! Я бот для регистрации на сайте LukInterLab.\n'
        'Для регистрации отправьте мне команду /register'
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управлять процессом регистрации."""
    user = update.effective_user
    
    # Проверьте, зарегистрирован ли пользователь уже
    if TelegramUser.objects.filter(telegram_id=user.id).exists():
        await update.message.reply_text(
            'Вы уже зарегистрированы на сайте!'
        )
        return

    # Создать нового пользователя
    try:
        TelegramUser.objects.create(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        await update.message.reply_text(
            'Регистрация успешно завершена! Теперь вы можете войти на сайт, используя свой Telegram ID.'
        )
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        await update.message.reply_text(
            'Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.'
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправьте сообщение при выполнении команды /справки."""
    await update.message.reply_text(
        'Доступные команды:\n'
        '/start - Начать работу с ботом\n'
        '/register - Зарегистрироваться на сайте\n'
        '/help - Показать это сообщение'
    )

def run_bot():
    """Start the bot."""
    # Создайте приложение
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("help", help_command))

    # Start the Bot
    application.run_polling() 