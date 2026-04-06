"""
Задачи Django-Q для автоматической генерации статей
"""
import logging
import os
import time
import sys
import platform
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Q
from django_q.models import Schedule
from datetime import timedelta

from .models import AISchedule

# Имя func у расписаний автопостинга в Django-Q (единая строка для фильтров и очистки)
SCHEDULE_TASK_FUNC = 'Assistant.tasks.run_schedule_task'
# Единый тик: раз в минуту ставит в очередь due-расписания
TICK_SCHEDULE_FUNC = 'Assistant.tasks.tick_ai_schedules'
AI_TICK_SCHEDULE_NAME = 'ai_schedules_minute_tick'
# Префикс канонического имени расписания в ORM Django-Q (легаси, для очистки)
AI_SCHEDULE_NAME_PREFIX = 'ai_schedule_'
# Lazy-import ArticleGeneratorService в run_schedule_task — иначе при старте тянутся bs4/lxml.

logger = logging.getLogger(__name__)

# Кроссплатформенная блокировка файлов
if platform.system() == 'Windows':
    # Для Windows используем msvcrt или альтернативу
    try:
        import msvcrt
        HAS_FILE_LOCK = True
        LOCK_TYPE = 'msvcrt'
    except ImportError:
        # Если msvcrt недоступен, используем простую блокировку на основе файла
        HAS_FILE_LOCK = True
        LOCK_TYPE = 'simple'
else:
    # Для Linux/Unix используем fcntl
    try:
        import fcntl
        HAS_FILE_LOCK = True
        LOCK_TYPE = 'fcntl'
    except ImportError:
        HAS_FILE_LOCK = False
        LOCK_TYPE = None

# Константы для блокировки и задержки
LOCK_FILE = Path(settings.BASE_DIR) / 'tmp' / 'autoposting.lock'
TASK_DELAY_MINUTES = 3  # Задержка между задачами в минутах
MAX_WAIT_TIME_MINUTES = 30  # Максимальное время ожидания блокировки
LOCK_FILE_MAX_AGE_MINUTES = 60  # Максимальный возраст lock файла (если старше - считается зависшим)


def _check_and_cleanup_stale_lock(lock_file_path):
    """
    Проверяет и очищает зависшие блокировки
    
    Args:
        lock_file_path: Путь к lock файлу
    
    Returns:
        bool: True если блокировка была очищена или не существует, False если блокировка активна
    """
    try:
        if not lock_file_path.exists():
            return True  # Блокировки нет - можно работать
        
        # Проверяем возраст файла
        file_age_seconds = time.time() - lock_file_path.stat().st_mtime
        file_age_minutes = file_age_seconds / 60
        
        if file_age_minutes > LOCK_FILE_MAX_AGE_MINUTES:
            logger.warning(f"[LOCK] Обнаружен зависший lock файл (возраст {file_age_minutes:.1f} минут). Удаляем...")
            return _force_delete_lock_file(lock_file_path, "зависший lock файл")
        
        # Проверяем существует ли процесс из lock файла
        try:
            with open(lock_file_path, 'r') as f:
                lock_content = f.read().strip()
                if lock_content:
                    parts = lock_content.split(':')
                    if len(parts) >= 1:
                        pid = int(parts[0])
                        # Проверяем существует ли процесс (кроссплатформенная проверка)
                        process_exists = _check_process_exists(pid)
                        if process_exists:
                            logger.info(f"[LOCK] Процесс {pid} существует - блокировка активна")
                            return False  # Процесс существует - блокировка активна
                        else:
                            logger.warning(f"[LOCK] Процесс {pid} не существует - блокировка зависла. Удаляем...")
                            return _force_delete_lock_file(lock_file_path, "зависший lock файл от несуществующего процесса")
        except Exception as e:
            logger.warning(f"[LOCK] Ошибка чтения lock файла: {str(e)}. Удаляем...")
            try:
                lock_file_path.unlink()
                return True
            except:
                return False
        
        return False  # Блокировка активна
        
    except Exception as e:
        logger.error(f"[LOCK] Ошибка проверки lock файла: {str(e)}")
        return False  # В случае ошибки считаем что блокировка активна


def _check_process_exists(pid):
    """
    Проверяет существует ли процесс с указанным PID (кроссплатформенная)
    
    Args:
        pid: ID процесса
    
    Returns:
        bool: True если процесс существует, False если нет
    """
    try:
        if platform.system() == 'Windows':
            # Windows: используем os.kill с сигналом 0 (может не работать на старых версиях)
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                # Если os.kill не работает, используем другой метод
                try:
                    import subprocess
                    # Используем tasklist для проверки процесса на Windows
                    result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                          capture_output=True, text=True, timeout=2)
                    # Если процесс найден, в выводе будет информация о нем
                    return str(pid) in result.stdout and 'PID' in result.stdout
                except Exception:
                    # Если и это не работает - считаем что процесс не существует
                    return False
        else:
            # Linux/Unix: используем os.kill
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False
    except Exception:
        return False


def _force_delete_lock_file(lock_file_path, description=""):
    """
    Принудительно удаляет lock файл на Windows и Linux
    
    Args:
        lock_file_path: Путь к lock файлу
        description: Описание файла для логов
    
    Returns:
        bool: True если файл удален, False если не удалось
    """
    try:
        if not lock_file_path.exists():
            return True  # Файл уже удален
        
        if platform.system() == 'Windows':
            # Windows: используем несколько методов для удаления заблокированного файла
            # Метод 1: Попытка обычного удаления
            try:
                lock_file_path.unlink()
                logger.info(f"[LOCK] {description} удален (обычное удаление)")
                return True
            except (OSError, PermissionError):
                pass  # Файл заблокирован, пробуем другие методы
            
            # Метод 2: Переименование с последующим удалением
            try:
                backup_name = lock_file_path.with_suffix('.lock.old')
                if backup_name.exists():
                    backup_name.unlink(missing_ok=True)
                lock_file_path.rename(backup_name)
                time.sleep(0.2)  # Небольшая задержка для освобождения блокировки
                backup_name.unlink()
                logger.info(f"[LOCK] {description} удален (через переименование)")
                return True
            except (OSError, PermissionError):
                pass  # Не получилось, пробуем следующий метод
            
            # Метод 3: Удаление через os.remove с retry
            try:
                for attempt in range(3):
                    try:
                        os.remove(str(lock_file_path))
                        if not lock_file_path.exists():
                            logger.info(f"[LOCK] {description} удален (через os.remove, попытка {attempt + 1})")
                            return True
                        time.sleep(0.1 * (attempt + 1))  # Увеличиваем задержку с каждой попыткой
                    except (OSError, PermissionError):
                        if attempt < 2:
                            time.sleep(0.2)
                            continue
                        raise
            except Exception:
                pass
            
            # Метод 4: Если файл все еще существует - помечаем как удаленный через переименование
            try:
                if lock_file_path.exists():
                    # Переименовываем с отметкой времени для последующей очистки
                    timestamp = int(time.time())
                    old_name = lock_file_path.with_name(f'autoposting.lock.old_{timestamp}')
                    lock_file_path.rename(old_name)
                    logger.warning(f"[LOCK] {description} переименован в {old_name.name} (файл был заблокирован, будет удален позже)")
                    # Файл будет считаться удаленным для текущей задачи
                    return True
            except Exception:
                pass
            
            logger.warning(f"[LOCK] Не удалось удалить {description} - файл заблокирован процессом")
            return False
        else:
            # Linux/Unix: обычное удаление должно работать
            try:
                lock_file_path.unlink()
                logger.info(f"[LOCK] {description} удален")
                return True
            except Exception as e:
                logger.warning(f"[LOCK] Ошибка удаления {description}: {str(e)}")
                return False
                
    except Exception as e:
        logger.error(f"[LOCK] Критическая ошибка при удалении lock файла: {str(e)}")
        return False


def run_schedule_task(schedule_id, force=False):
    """
    Задача для генерации статей по расписанию с блокировкой для последовательного выполнения
    
    Args:
        schedule_id: ID расписания (int или str)
        force: если True (ручной запуск), не проверяем next_run > сейчас
    """
    lock_file_path = None
    lock_file = None
    
    try:
        # Преобразуем в int, если передана строка
        schedule_id = int(schedule_id)
        force = bool(force)
        schedule_obj = AISchedule.objects.get(id=schedule_id, is_active=True)
        
        # Создаем директорию для lock файла если не существует
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        lock_file_path = LOCK_FILE
        
        # Проверяем и очищаем зависшие блокировки перед попыткой получить блокировку
        if lock_file_path.exists():
            if _check_and_cleanup_stale_lock(lock_file_path):
                logger.info(f"[LOCK] Зависшие блокировки очищены")
            else:
                logger.info(f"[LOCK] Активная блокировка обнаружена, ожидание...")
        
        # Ожидание и получение блокировки
        wait_start = time.time()
        max_wait_seconds = MAX_WAIT_TIME_MINUTES * 60
        
        logger.info(f"[LOCK] Попытка получить блокировку для задачи schedule_id={schedule_id}...")
        
        # Пытаемся получить блокировку с таймаутом
        while True:
            # Перед каждой попыткой проверяем зависшие блокировки
            if lock_file_path.exists():
                _check_and_cleanup_stale_lock(lock_file_path)
            try:
                # Открываем файл в режиме записи
                lock_file = open(lock_file_path, 'w')
                
                # Пытаемся получить эксклюзивную блокировку (кроссплатформенная)
                if LOCK_TYPE == 'fcntl':
                    # Linux/Unix: используем fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif LOCK_TYPE == 'msvcrt':
                    # Windows: используем msvcrt (требует специальный режим открытия файла)
                    try:
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    except (IOError, OSError):
                        lock_file.close()
                        raise IOError("File locked by another process")
                elif LOCK_TYPE == 'simple':
                    # Windows: простая блокировка - проверяем может ли файл быть открыт
                    # Если файл уже существует и не старый - считаем что заблокирован
                    if lock_file_path.exists():
                        file_age = time.time() - lock_file_path.stat().st_mtime
                        if file_age < 60:  # Файл моложе 60 секунд - считаем заблокированным
                            lock_file.close()
                            raise IOError("File locked by another process")
                
                # Успешно получили блокировку
                lock_file.write(f"{os.getpid()}:{schedule_id}:{timezone.now().isoformat()}\n")
                lock_file.flush()
                logger.info(f"[LOCK] Блокировка получена для schedule_id={schedule_id} (тип: {LOCK_TYPE})")
                break
                
            except (IOError, OSError, ImportError):
                # Файл заблокирован другой задачей
                if lock_file:
                    try:
                        lock_file.close()
                    except:
                        pass
                    lock_file = None
                
                elapsed = time.time() - wait_start
                if elapsed > max_wait_seconds:
                    logger.error(f"[LOCK] Превышено время ожидания блокировки ({MAX_WAIT_TIME_MINUTES} минут)")
                    return {
                        'success': False,
                        'error': f'Lock timeout after {MAX_WAIT_TIME_MINUTES} minutes'
                    }
                
                wait_seconds = min(10, max_wait_seconds - elapsed)  # Ждем максимум 10 секунд перед повтором
                logger.info(f"[LOCK] Блокировка занята. Ожидание {int(wait_seconds)} секунд перед повтором...")
                time.sleep(wait_seconds)

        # Блокировка получена, выполняем задачу
        try:
            logger.info(f"[START] Запуск генерации по расписанию: {schedule_obj.name}")

            schedule_obj.refresh_from_db()
            if not schedule_obj.is_active:
                logger.info(f"[SKIP] Расписание {schedule_id} неактивно")
                return {'success': False, 'skipped': 'inactive'}
            if schedule_obj.max_schedule_runs is not None:
                if schedule_obj.completed_schedule_runs >= schedule_obj.max_schedule_runs:
                    logger.info(f"[SKIP] Лимит запусков для {schedule_id}")
                    return {'success': False, 'skipped': 'max_runs'}
            now_check = timezone.now()
            if not force and schedule_obj.next_run and schedule_obj.next_run > now_check:
                logger.info(f"[SKIP] Ещё не время next_run={schedule_obj.next_run}")
                return {'success': False, 'skipped': 'not_due'}

            from .article_generator import ArticleGeneratorService

            generator = ArticleGeneratorService(schedule_obj)
            
            # Генерируем статьи
            generated_posts = generator.generate_batch()
            
            logger.info(f"[OK] Генерация завершена: создано {len(generated_posts)} статей")
            
            # Задержка после выполнения для распределения нагрузки (3 минуты между задачами)
            logger.info(f"[DELAY] Ожидание {TASK_DELAY_MINUTES} минут перед следующей задачей...")
            time.sleep(TASK_DELAY_MINUTES * 60)
            
            schedule_obj.refresh_from_db()
            schedule_obj.sync_next_run_after(timezone.now())
            schedule_obj.last_run = timezone.now()
            schedule_obj.completed_schedule_runs += 1
            _fields = ['next_run', 'last_run', 'completed_schedule_runs']
            if (
                schedule_obj.max_schedule_runs is not None
                and schedule_obj.completed_schedule_runs >= schedule_obj.max_schedule_runs
            ):
                schedule_obj.is_active = False
                _fields.append('is_active')
                logger.info(f"[OK] Расписание {schedule_id} выключено: достигнут лимит запусков")
            schedule_obj.save(update_fields=_fields)

            return {
                'success': True,
                'schedule_id': schedule_id,
                'generated_count': len(generated_posts),
                'posts': [post.id for post in generated_posts]
            }
            
        finally:
            # Освобождаем блокировку
            if lock_file:
                try:
                    if LOCK_TYPE == 'fcntl':
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    elif LOCK_TYPE == 'msvcrt':
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    lock_file.close()
                    logger.info(f"[LOCK] Блокировка освобождена для schedule_id={schedule_id}")
                except:
                    pass
                lock_file = None
        
    except AISchedule.DoesNotExist:
        logger.error(f"[ERROR] Расписание {schedule_id} не найдено или неактивно")
        return {'success': False, 'error': 'Schedule not found or inactive'}
    except Exception as e:
        logger.error(f"[ERROR] Ошибка генерации по расписанию {schedule_id}: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}
    finally:
        # Убеждаемся что блокировка освобождена
        if lock_file:
            try:
                if LOCK_TYPE == 'fcntl':
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                elif LOCK_TYPE == 'msvcrt':
                    try:
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    except:
                        pass
                lock_file.close()
            except:
                pass
        # Пытаемся удалить lock файл если он пустой
        if lock_file_path and os.path.exists(lock_file_path):
            try:
                if os.path.getsize(lock_file_path) == 0:
                    os.remove(lock_file_path)
            except:
                pass


def tick_ai_schedules():
    """
    Раз в минуту: поставить в очередь run_schedule_task для расписаний,
    у которых наступило next_run и не исчерпан лимит запусков.
    """
    now = timezone.now()
    due = AISchedule.objects.filter(
        is_active=True,
        next_run__lte=now,
    ).filter(
        Q(max_schedule_runs__isnull=True) | Q(completed_schedule_runs__lt=F('max_schedule_runs'))
    ).values_list('id', flat=True)
    due_ids = list(due)
    if not due_ids:
        return {'queued': 0}
    try:
        from django_q.tasks import async_task
    except ImportError:
        async_task = None
    if not async_task:
        logger.error('[ERROR] django_q.async_task недоступен')
        return {'queued': 0, 'error': 'no async_task'}
    for sid in due_ids:
        async_task(SCHEDULE_TASK_FUNC, sid)
        logger.info(f"[TICK] В очереди run_schedule_task({sid})")
    return {'queued': len(due_ids)}


def ai_schedules_monitoring_items():
    """Строки для таблицы мониторинга: минутный тик + активные AISchedule."""
    items = []
    tick = Schedule.objects.filter(name=AI_TICK_SCHEDULE_NAME).first()
    if tick:
        items.append({
            'kind': 'tick',
            'label': 'Опрос расписаний статей (каждую минуту)',
            'cron': tick.cron or '* * * * *',
            'last_run': tick.last_run,
            'next_run': tick.next_run,
            'ai_schedule': None,
        })
    for s in AISchedule.objects.filter(is_active=True).order_by('name'):
        items.append({
            'kind': 'ai',
            'label': s.name,
            'cron': s.get_interval_summary(),
            'last_run': s.last_run,
            'next_run': s.next_run,
            'ai_schedule': s,
        })
    return items


def schedules_for_monitoring():
    """Легаси-хук: django-q записи ai_schedule_<id> больше не используются."""
    return []


def setup_schedules():
    """
    Один глобальный CRON в Django-Q: каждую минуту tick_ai_schedules.
    Старые записи run_schedule_task на каждое AISchedule удаляются.
    """
    with transaction.atomic():
        legacy_n, _ = Schedule.objects.filter(name__startswith='ai_autoposting_').delete()
        if legacy_n:
            logger.info(
                '[OK] Удалены легаси-расписания django-q ai_autoposting_* (%s шт.)',
                legacy_n,
            )

        removed, _ = Schedule.objects.filter(func=SCHEDULE_TASK_FUNC).delete()
        if removed:
            logger.info(
                '[OK] Удалены старые задачи %s (записей: %s)',
                SCHEDULE_TASK_FUNC,
                removed,
            )

        tick, created = Schedule.objects.update_or_create(
            name=AI_TICK_SCHEDULE_NAME,
            defaults={
                'func': TICK_SCHEDULE_FUNC,
                'schedule_type': Schedule.CRON,
                'cron': '* * * * *',
                'repeats': -1,
                'args': '',
            },
        )
        action = 'создано' if created else 'обновлено'
        logger.info(
            '[OK] Минутный опрос расписаний статей %s (CRON * * * * *)',
            action,
        )


def remove_schedule(schedule_id: int):
    """Удалить из Django-Q все задачи автопостинга с данным id (канонические и легаси)."""
    deleted, _ = Schedule.objects.filter(
        func=SCHEDULE_TASK_FUNC,
        args=str(schedule_id),
    ).delete()
    if deleted:
        logger.info(
            '[OK] Удалено расписаний Django-Q для schedule_id=%s: %s',
            schedule_id,
            deleted,
        )
    else:
        logger.warning(
            '[WARNING] Расписание Django-Q для schedule_id=%s не найдено',
            schedule_id,
        )

