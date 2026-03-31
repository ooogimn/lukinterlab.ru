"""
Улучшенная обработка ошибок GigaChat API
"""
import logging
import time
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)


class GigaChatErrorHandler:
    """Обработчик ошибок GigaChat API с автоматическим retry"""
    
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 5]  # Задержки в секундах для каждой попытки
    
    @staticmethod
    def handle_error(response: requests.Response, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """
        Обработать ошибку API и вернуть рекомендации по действию
        
        Returns:
            Dict с рекомендациями или None
        """
        status = response.status_code
        
        if status == 200:
            return {'action': 'success'}
        
        error_info = {
            'status_code': status,
            'response_text': response.text[:500],
            'retry_count': retry_count,
        }
        
        if status == 401:
            # Токен истек или неверный
            logger.warning("GigaChat: Токен истек или неверный (401)")
            return {
                'action': 'refresh_token',
                'retry': retry_count < GigaChatErrorHandler.MAX_RETRIES,
                'error': 'Токен доступа истек. Требуется обновление.',
                **error_info
            }
        
        elif status == 429:
            # Rate limit превышен
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.warning(f"GigaChat: Rate limit превышен (429). Retry-After: {retry_after}с")
            return {
                'action': 'rate_limit',
                'retry': retry_count < GigaChatErrorHandler.MAX_RETRIES,
                'retry_after': retry_after,
                'error': f'Превышен лимит запросов. Повторить через {retry_after} секунд.',
                **error_info
            }
        
        elif status == 400:
            # Неверный запрос
            logger.error(f"GigaChat: Неверный запрос (400): {response.text[:200]}")
            return {
                'action': 'invalid_request',
                'retry': False,
                'error': 'Неверный формат запроса. Проверьте параметры.',
                **error_info
            }
        
        elif status == 403:
            # Доступ запрещен
            logger.error("GigaChat: Доступ запрещен (403)")
            return {
                'action': 'forbidden',
                'retry': False,
                'error': 'Доступ запрещен. Проверьте права доступа и scope.',
                **error_info
            }
        
        elif status >= 500:
            # Серверная ошибка
            logger.error(f"GigaChat: Серверная ошибка ({status})")
            return {
                'action': 'server_error',
                'retry': retry_count < 2,  # Меньше попыток для серверных ошибок
                'error': 'Ошибка сервера GigaChat. Повторите позже.',
                **error_info
            }
        
        else:
            # Неизвестная ошибка
            logger.error(f"GigaChat: Неизвестная ошибка ({status})")
            return {
                'action': 'unknown_error',
                'retry': retry_count < GigaChatErrorHandler.MAX_RETRIES,
                'error': f'Неизвестная ошибка: {status}',
                **error_info
            }
    
    @staticmethod
    def should_retry(error_info: Dict[str, Any]) -> bool:
        """Определить, нужно ли повторить запрос"""
        return error_info.get('retry', False)
    
    @staticmethod
    def get_retry_delay(error_info: Dict[str, Any], retry_count: int) -> float:
        """Получить задержку перед повторной попыткой"""
        if error_info.get('action') == 'rate_limit':
            return float(error_info.get('retry_after', 60))
        
        # Экспоненциальная задержка
        if retry_count < len(GigaChatErrorHandler.RETRY_DELAYS):
            return GigaChatErrorHandler.RETRY_DELAYS[retry_count]
        
        return 5.0  # Максимальная задержка
    
    @staticmethod
    def log_error_for_admin(error_info: Dict[str, Any]):
        """Логировать ошибку для администратора"""
        # TODO: Отправить уведомление администратору через Telegram/Email
        logger.error(f"GigaChat API Error: {error_info}")

