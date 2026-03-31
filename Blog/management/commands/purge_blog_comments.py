"""
Удаление всех комментариев к статьям блога и связанных записей CommentModeration.
Используйте только осознанно: восстановление из бэкапа, если нужно.

На SQLite при строгих FK коммит часто падает с FOREIGN KEY constraint failed
(порядок каскадов + самоссылка MPTT). По умолчанию на sqlite на время команды
отключается PRAGMA foreign_keys (только для этого соединения).

Комментарии удаляются пачками (по умолчанию 100 «листьев» дерева). Если пачка
падает (битая страница SQLite, FK и т.д.) — та же пачка обрабатывается по одному
pk; неудаляемые pk пропускаются и выводятся в конце.

Если DELETE по CommentModeration даёт database disk image is malformed, запускайте
с --comments-only (и при необходимости --skip-integrity-check). Блок модерации
при ошибке БД пропускается автоматически с предупреждением.
"""
from contextlib import contextmanager

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction
from django.db.models import Count
from django.db.utils import IntegrityError

from Blog.models import Comment
from Moderation.models import CommentModeration, ModerationNotification


def _sqlite_quick_check():
    """True, None если целостность в порядке; иначе False и текст ошибки."""
    if connection.vendor != 'sqlite':
        return True, None
    try:
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA quick_check')
            rows = cursor.fetchall()
    except DatabaseError as exc:
        return False, str(exc)
    if not rows:
        return True, None
    first = rows[0][0]
    if first == 'ok':
        return True, None
    lines = [str(r[0]) for r in rows[:40]]
    return False, '\n'.join(lines)


@contextmanager
def _noop_cm():
    yield


@contextmanager
def _sqlite_relax_foreign_keys():
    """PRAGMA вне транзакции; после блока проверки FK снова включаются."""
    if connection.vendor != 'sqlite':
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA foreign_keys = OFF')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA foreign_keys = ON')


def _delete_comments_in_chunks(
    chunk_size,
    style,
    stderr,
    *,
    fast_bulk,
    use_sqlite_pragma,
):
    """
    Возвращает (сколько строк затронуто delete(), отсортированный список битых pk).
    """
    if fast_bulk and (connection.vendor != 'sqlite' or use_sqlite_pragma):
        n, _ = Comment.objects.all().delete()
        return n, []

    deleted_total = 0
    bad_skip = set()
    batch_no = 0

    while Comment.objects.exists():
        batch_no += 1
        qs = (
            Comment.objects.annotate(_child_n=Count('children'))
            .filter(_child_n=0)
            .order_by('pk')
        )
        if bad_skip:
            qs = qs.exclude(pk__in=bad_skip)
        leaf_ids = list(qs.values_list('pk', flat=True)[:chunk_size])

        if not leaf_ids:
            pk_any = (
                Comment.objects.exclude(pk__in=bad_skip)
                .order_by('pk')
                .values_list('pk', flat=True)
                .first()
            )
            if pk_any is None:
                rest = Comment.objects.count()
                stderr.write(
                    style.WARNING(
                        f'Не осталось кандидатов к удалению (кроме {len(bad_skip)} '
                        f'помеченных как битые). Всего записей Comment: {rest}.'
                    )
                )
                break
            leaf_ids = [pk_any]

        try:
            with transaction.atomic():
                n, _ = Comment.objects.filter(pk__in=leaf_ids).delete()
                deleted_total += n
        except (DatabaseError, IntegrityError) as exc:
            stderr.write(
                style.WARNING(
                    f'Пачка #{batch_no} ({len(leaf_ids)} шт., pk {leaf_ids[0]}…): '
                    f'массовое удаление не прошло ({exc}). Поштучно…'
                )
            )
            for pk in leaf_ids:
                if pk in bad_skip:
                    continue
                try:
                    with transaction.atomic():
                        n, _ = Comment.objects.filter(pk=pk).delete()
                        deleted_total += n
                except (DatabaseError, IntegrityError) as err:
                    stderr.write(
                        style.ERROR(
                            f'Не удалось удалить Comment pk={pk}: {err}'
                        )
                    )
                    bad_skip.add(pk)

    bad_list = sorted(bad_skip)
    if bad_list:
        stderr.write(
            style.ERROR(
                f'Итого не удалено (битые/заблокированные) pk: {bad_list}. '
                'Можно в sqlite3: SELECT * FROM app_comments WHERE id IN (...);'
            )
        )

    return deleted_total, bad_list


class Command(BaseCommand):
    help = (
        'Удалить ВСЕ комментарии Blog.Comment и (по умолчанию) связанную модерацию. '
        'Требуется --yes. SQLite: PRAGMA quick_check, если не передан --skip-integrity-check. '
        'При битой таблице модерации: --comments-only.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Подтверждение необратимого удаления',
        )
        parser.add_argument(
            '--enforce-fk',
            action='store_true',
            help='SQLite: не отключать foreign_keys (может снова выдать IntegrityError).',
        )
        parser.add_argument(
            '--skip-integrity-check',
            action='store_true',
            help='Не вызывать PRAGMA quick_check (только если осознанно).',
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=100,
            help='Сколько «листьев» комментариев за одну транзакцию (по умолчанию 100).',
        )
        parser.add_argument(
            '--fast-bulk',
            action='store_true',
            help='Один Comment.objects.all().delete() (целая БД; на SQLite — с отключением FK).',
        )
        parser.add_argument(
            '--comments-only',
            action='store_true',
            help='Не трогать ModerationNotification и CommentModeration (если эти таблицы '
            'битые и DELETE падает с malformed — используйте этот флаг).',
        )

    def handle(self, *args, **options):
        if not options['yes']:
            self.stderr.write(
                self.style.ERROR(
                    'Отказ: передайте --yes для удаления всех комментариев блога.'
                )
            )
            return

        chunk_size = max(1, options['chunk_size'])

        if (
            connection.vendor == 'sqlite'
            and not options['skip_integrity_check']
        ):
            ok, detail = _sqlite_quick_check()
            if not ok:
                raise CommandError(
                    'SQLite: база повреждена или PRAGMA quick_check не прошёл.\n'
                    'Типичное сообщение: database disk image is malformed — это не баг '
                    'команды purge, а битый файл db.sqlite3 (часто из-за одновременного '
                    'доступа: runserver + тяжёлые операции, сбой диска).\n\n'
                    'Сделайте так:\n'
                    '  1) Остановите runserver, qcluster и всё, что открывает БД.\n'
                    '  2) Скопируйте db.sqlite3 в безопасное место.\n'
                    '  3) Проверка: sqlite3 db.sqlite3 "PRAGMA integrity_check;"\n'
                    '  4) Восстановление (пример): '
                    'sqlite3 db.sqlite3 ".recover" | sqlite3 db_recovered.sqlite3\n'
                    '     затем замените файл или укажите его в DATABASES.\n'
                    '  5) Или восстановите БД с бэкапа хостинга.\n\n'
                    'Если нужно всё равно чистить данные, повторите с '
                    '--skip-integrity-check (на свой риск).\n'
                    f'Детали quick_check: {detail}'
                )

        comments_only = options['comments_only']
        use_sqlite_pragma = (
            connection.vendor == 'sqlite' and not options['enforce_fk']
        )
        ctx = _sqlite_relax_foreign_keys() if use_sqlite_pragma else _noop_cm()
        fast_bulk = options['fast_bulk']

        n_comments_before = Comment.objects.count()
        n_notif = 0
        mod_deleted = 0
        mod_detail = {}

        with ctx:
            if not comments_only:
                ct = ContentType.objects.get_for_model(Comment)
                mod_qs = CommentModeration.objects.filter(content_type=ct)
                try:
                    with transaction.atomic():
                        n_notif, _ = ModerationNotification.objects.filter(
                            comment_moderation__in=mod_qs
                        ).delete()
                        mod_deleted, mod_detail = mod_qs.delete()
                except DatabaseError as exc:
                    self.stderr.write(
                        self.style.WARNING(
                            f'Удаление уведомлений/модерации комментариев не выполнено '
                            f'({exc}). Продолжаем только Blog.Comment. '
                            f'При повторном запуске можно сразу указать --comments-only.'
                        )
                    )
            else:
                self.stdout.write(
                    'Режим --comments-only: ModerationNotification и CommentModeration не изменяются.'
                )

            comments_deleted, bad_list = _delete_comments_in_chunks(
                chunk_size,
                self.style,
                self.stderr,
                fast_bulk=fast_bulk,
                use_sqlite_pragma=use_sqlite_pragma,
            )

        mod_part = (
            'модерация не трогалась.'
            if comments_only
            else (
                f'уведомлений: {n_notif}; объектов при удалении модерации: {mod_deleted}.'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'{mod_part} '
                f'Удалено комментариев (строк каскадом): {comments_deleted} '
                f'(было {n_comments_before}).'
            )
        )
        if bad_list:
            self.stdout.write(
                self.style.WARNING(f'Не удалённые pk: {bad_list}')
            )
        if mod_detail and not comments_only:
            self.stdout.write(str(mod_detail))
