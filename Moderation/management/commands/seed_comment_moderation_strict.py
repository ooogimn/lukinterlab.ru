"""
Создаёт или обновляет строгий набор критериев модерации комментариев
(удаление при спаме/мате, лимит ссылок, базовые спам-фразы).
"""
from django.core.management.base import BaseCommand

from Moderation.models import CommentModerationCriteria

DEFAULT_NAME = 'Строгая модерация (блог и прочие комментарии)'

# Подстроковый поиск (нижний регистр в коде); не добавлять слишком короткие шаблоны
DEFAULT_SPAM_PATTERNS = [
    'viagra',
    'cialis',
    'casino',
    'криптовалют',
    'заработок в интернет',
    'пассивный доход',
    'перейдите по ссылке',
    'перейти по ссылке',
    'регистрация бонус',
    'telegram.me/',
    't.me/',
    'whatsapp',
    'seo продвижение за',
]

DEFAULT_FORBIDDEN = [
    'хуй',
    'пизд',
    'ебан',
    'бляд',
]


class Command(BaseCommand):
    help = (
        'Создать/обновить активные критерии модерации комментариев (строгий пресет). '
        'С флагом --replace отключаются остальные активные наборы.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Снять is_active со всех остальных CommentModerationCriteria',
        )
        parser.add_argument(
            '--name',
            type=str,
            default=DEFAULT_NAME,
            help=f'Имя набора (по умолчанию: {DEFAULT_NAME})',
        )

    def handle(self, *args, **options):
        name = options['name']
        if options['replace']:
            n = CommentModerationCriteria.objects.filter(is_active=True).update(
                is_active=False
            )
            self.stdout.write(f'Деактивировано наборов критериев: {n}')

        criteria_payload = {
            'min_length': 2,
            'max_length': 4000,
            'max_urls': 1,
            'forbidden_words': DEFAULT_FORBIDDEN,
            'spam_patterns': DEFAULT_SPAM_PATTERNS,
        }
        actions_payload = {
            'delete': True,
            'correct': False,
            'reply': False,
        }

        obj, created = CommentModerationCriteria.objects.update_or_create(
            name=name,
            defaults={
                'description': (
                    'Автоматически: спам/запрещённые слова и более одной ссылки — удаление; '
                    'прочие нарушения без действия — скрытие (см. CommentModerationService).'
                ),
                'criteria': criteria_payload,
                'actions': actions_payload,
                'is_active': True,
            },
        )

        verb = 'Создан' if created else 'Обновлён'
        self.stdout.write(
            self.style.SUCCESS(
                f'{verb} набор критериев id={obj.pk} «{obj.name}» (is_active=True).'
            )
        )
