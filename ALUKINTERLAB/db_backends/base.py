"""
Кастомный database backend для SQLite с поддержкой WAL mode
для предотвращения блокировок базы данных
"""
from django.db.backends.sqlite3.base import (
    DatabaseWrapper as SQLiteDatabaseWrapper,
    Database,
)
import logging

logger = logging.getLogger(__name__)


class DatabaseWrapper(SQLiteDatabaseWrapper):
    """
    Расширенный wrapper для SQLite с автоматической настройкой WAL mode
    и оптимизацией для production
    """
    
    def get_new_connection(self, conn_params):
        """
        Создаёт новое соединение с SQLite и настраивает WAL mode
        """
        conn = super().get_new_connection(conn_params)
        
        try:
            # Включаем WAL mode для лучшей производительности и меньших блокировок
            # В Python 3.13 sqlite3.Cursor не поддерживает контекстный менеджер напрямую
            cursor = conn.cursor()
            try:
                # Устанавливаем WAL mode (Write-Ahead Logging)
                cursor.execute("PRAGMA journal_mode=WAL;")
                # Увеличиваем timeout для операций
                cursor.execute("PRAGMA busy_timeout=30000;")  # 30 секунд
                # Оптимизация для production
                cursor.execute("PRAGMA synchronous=NORMAL;")  # Баланс между безопасностью и скоростью
                cursor.execute("PRAGMA cache_size=-64000;")  # 64MB кэша
                cursor.execute("PRAGMA foreign_keys=ON;")  # Включаем внешние ключи
                
                # Получаем текущий режим журнала (без логирования)
                cursor.execute("PRAGMA journal_mode;")
                journal_mode = cursor.fetchone()[0]
                # Логирование отключено по запросу пользователя
            finally:
                cursor.close()
                
        except Exception as e:
            logger.warning(f"Failed to set SQLite PRAGMA settings: {e}")
            # Продолжаем работу даже если не удалось установить настройки
        
        return conn

