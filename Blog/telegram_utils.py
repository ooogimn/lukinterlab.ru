import requests
from django.conf import settings
from datetime import datetime
from django.core.files.storage import default_storage
import os
import logging

logger = logging.getLogger(__name__)

def send_to_telegram(post):
    """
    Отправьте сообщение в Telegram-канал с изображением и отформатированным сообщением
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHANNEL_ID:
        logger.error("Настройки Telegram не настроены")
        return False
        
    bot_token = settings.TELEGRAM_BOT_TOKEN
    channel_id = settings.TELEGRAM_CHANNEL_ID
    
    # Получаем полный URL сайта
    site_url = settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://lukinterlab.ru'
    
    # Подготовьте текст сообщения
    # Формат: Заголовок + Описание (первые 200 слов) + Ссылка "Читать далее"
    message = f"*{post.title}*\n\n"
    if post.description:
        message += f"{post.description}\n\n"
    message += f"👉 [Читать далее]({site_url}{post.get_absolute_url()})"
    
    logger.info(f"Попытка отправить сообщение '{post.title}' to Telegram")
    
    # Сначала попробуйте отправить фотографию с подписью
    if post.kartinka:
        image_file = None
        try:
            # Получите полный путь к изображению
            image_path = post.kartinka.path
            
            if not os.path.exists(image_path):
                logger.error(f"Изображение не найдено: {image_path}")
                raise FileNotFoundError(f"Изображение не найдено: {image_path}")
            
            # Подготовьте URL API для отправки фотографии
            api_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            
            # Открываем файл с правильным закрытием
            image_file = open(image_path, 'rb')
            
            # Подготовка файлов и данных
            files = {
                'photo': image_file
            }
            data = {
                'chat_id': channel_id,
                'caption': message,
                'parse_mode': 'Markdown'
            }
            
            # Отправьте фотографию с подписью
            response = requests.post(api_url, files=files, data=data, timeout=30)
            
            # Проверяем ответ API
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"Telegram API error (photo): {response.status_code} - {error_data}")
                raise Exception(f"Telegram API вернул ошибку: {response.status_code} - {error_data.get('description', 'Unknown error')}")
            
            response.raise_for_status()
            response_data = response.json()
            
            if not response_data.get('ok', False):
                error_info = response_data.get('description', 'Unknown error')
                logger.error(f"Telegram API вернул ok=False: {error_info}")
                raise Exception(f"Telegram API error: {error_info}")
            
            # Обновите поле telegram_posted_at в сообщении
            post.telegram_posted_at = datetime.now()
            post.save(update_fields=['telegram_posted_at'])
            
            logger.info(f"Successfully sent post '{post.title}' with image to Telegram")
            return True
            
        except FileNotFoundError as e:
            logger.error(f"Файл изображения не найден: {str(e)}")
            # Продолжаем отправку без изображения
        except Exception as e:
            logger.error(f"Ошибка отправки фото в Telegram: {str(e)}", exc_info=True)
            # Если отправить фотографию не удастся, вернитесь к отправке только текстового сообщения
        finally:
            # Закрываем файл если он был открыт
            if image_file:
                try:
                    image_file.close()
                except:
                    pass
        
        # Пытаемся отправить только текстовое сообщение
        try:
            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            data = {
                "chat_id": channel_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(api_url, data=data, timeout=30)
            
            # Проверяем ответ API
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"Telegram API error (message): {response.status_code} - {error_data}")
                raise Exception(f"Telegram API вернул ошибку: {response.status_code} - {error_data.get('description', 'Unknown error')}")
            
            response.raise_for_status()
            response_data = response.json()
            
            if not response_data.get('ok', False):
                error_info = response_data.get('description', 'Unknown error')
                logger.error(f"Telegram API вернул ok=False: {error_info}")
                raise Exception(f"Telegram API error: {error_info}")
            
            # Обновите поле telegram_posted_at в сообщении
            post.telegram_posted_at = datetime.now()
            post.save(update_fields=['telegram_posted_at'])
            
            logger.info(f"Successfully sent post '{post.title}' (text only) to Telegram")
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {str(e)}", exc_info=True)
            logger.error(f"Ошибка Telegram не опубликована: {post.title}")
            return False
    else:
        # Если изображения нет, просто отправьте сообщение
        try:
            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            data = {
                "chat_id": channel_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(api_url, data=data, timeout=30)
            
            # Проверяем ответ API
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                logger.error(f"Telegram API error (message): {response.status_code} - {error_data}")
                raise Exception(f"Telegram API вернул ошибку: {response.status_code} - {error_data.get('description', 'Unknown error')}")
            
            response.raise_for_status()
            response_data = response.json()
            
            if not response_data.get('ok', False):
                error_info = response_data.get('description', 'Unknown error')
                logger.error(f"Telegram API вернул ok=False: {error_info}")
                raise Exception(f"Telegram API error: {error_info}")
            
            # Обновите поле telegram_posted_at в сообщении
            post.telegram_posted_at = datetime.now()
            post.save(update_fields=['telegram_posted_at'])
            
            logger.info(f"Successfully sent post '{post.title}' (text only) to Telegram")
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {str(e)}", exc_info=True)
            logger.error(f"Ошибка Telegram не опубликована: {post.title}")
            return False 