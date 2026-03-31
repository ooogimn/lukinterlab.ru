"""
Кастомный обработчик логирования для Windows
Игнорирует ошибки ротации файлов, если файл занят другим процессом
"""
import logging
from logging.handlers import RotatingFileHandler
import os


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    Безопасный RotatingFileHandler для Windows
    Игнорирует PermissionError при ротации файлов
    """
    
    def doRollover(self):
        """
        Переопределяем метод ротации с обработкой ошибок
        """
        try:
            super().doRollover()
        except (PermissionError, OSError) as e:
            # Игнорируем ошибки доступа к файлу (файл занят другим процессом)
            # Логирование продолжит работать, просто ротация не произойдет
            pass
        except Exception:
            # Для других ошибок вызываем родительский метод
            raise

