"""
Разово приводит ArticleModeration в соответствие с Post.status:
у опубликованных статей статус модерации не должен оставаться «ожидает» / «доработка».
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from Moderation.models import ArticleModeration


class Command(BaseCommand):
    help = (
        'Проставить «Одобрено» записям модерации, у которых статья уже опубликована, '
        'а статус модерации ещё pending или needs_revision.'
    )

    def handle(self, *args, **options):
        qs = ArticleModeration.objects.filter(
            post__status='published',
            status__in=('pending', 'needs_revision'),
        )
        n = qs.update(status='approved', moderated_at=timezone.now())
        self.stdout.write(self.style.SUCCESS(f'Обновлено записей модерации: {n}'))
