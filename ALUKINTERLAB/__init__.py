"""
Настройка SQLite для работы с Django-Q
Применяется при каждом подключении к базе данных
"""
from django.db.backends.signals import connection_created

def configure_sqlite(sender, connection, **kwargs):
    """Настройка SQLite для лучшей параллельности"""
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            # WAL режим для лучшей параллельности чтения/записи
            cursor.execute("PRAGMA journal_mode=WAL;")
            # Увеличиваем timeout для ожидания разблокировки БД
            cursor.execute("PRAGMA busy_timeout=30000;")  # 30 секунд
            # Баланс между производительностью и надежностью
            cursor.execute("PRAGMA synchronous=NORMAL;")
            # Увеличиваем кэш для лучшей производительности
            cursor.execute("PRAGMA cache_size=-64000;")  # 64MB

# Подключаем сигнал для настройки SQLite
connection_created.connect(configure_sqlite)

