"""
Однократно после миграции identity_auth: создать LinkedSocialAccount
для пользователей со старыми username вида vkid_* / yandex_* / google_* / max_*.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from identity_auth.models import LinkedSocialAccount

User = get_user_model()

PREFIXES = (
    ('vkid_', 'vkid'),
    ('yandex_', 'yandex'),
    ('google_', 'google'),
    ('max_', 'max'),
)


class Command(BaseCommand):
    help = 'Заполнить LinkedSocialAccount из legacy username (после внедрения identity_auth).'

    def handle(self, *args, **options):
        created = 0
        for prefix, provider in PREFIXES:
            qs = User.objects.filter(username__startswith=prefix).only('id', 'username')
            for u in qs.iterator():
                uid = u.username[len(prefix) :]
                if not uid:
                    continue
                _, was_created = LinkedSocialAccount.objects.get_or_create(
                    provider=provider,
                    provider_user_id=uid,
                    defaults={'user': u},
                )
                if was_created:
                    created += 1
        self.stdout.write(self.style.SUCCESS(f'Новых привязок: {created}'))
