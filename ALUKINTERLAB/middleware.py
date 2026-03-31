"""
Middleware для правильного управления соединениями с базой данных
Особенно важно для SQLite чтобы избежать блокировок
"""
import logging
from django.db import connections

logger = logging.getLogger(__name__)


class DatabaseConnectionMiddleware:
    """
    Middleware для закрытия соединений с БД после каждого запроса
    Это критично для SQLite чтобы избежать блокировок
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Закрываем все соединения с БД после обработки запроса
        # Это предотвращает блокировки SQLite
        try:
            for conn in connections.all():
                conn.close()
        except Exception as e:
            logger.warning(f"Error closing database connections: {e}")
        
        return response

