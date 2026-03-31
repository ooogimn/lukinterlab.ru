"""
Тест автопоста VK: вызывает send_to_vk для одной статьи (как сигнал при первой публикации).

Примеры:
  python manage.py test_vk_autopost
  python manage.py test_vk_autopost --post-id 42
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from Blog.models import Post
from Blog.vk_utils import send_to_vk


class Command(BaseCommand):
    help = 'Отправить одну опубликованную статью на стену VK (для проверки токенов и wall.post).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--post-id',
            type=int,
            default=None,
            help='ID статьи (published, без vk_posted_at — иначе пост не уйдёт второй раз)',
        )

    def handle(self, *args, **options):
        if not settings.VK_ACCESS_TOKEN or not settings.VK_GROUP_ID:
            self.stderr.write(self.style.ERROR('Задайте VK_ACCESS_TOKEN и VK_GROUP_ID в .env'))
            return

        pid = options['post_id']
        if pid:
            try:
                post = Post.objects.get(pk=pid)
            except Post.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Пост id={pid} не найден'))
                return
        else:
            post = (
                Post.objects.filter(status='published', vk_posted_at__isnull=True)
                .order_by('-created')
                .first()
            )
            if not post:
                self.stderr.write(
                    self.style.WARNING(
                        'Нет опубликованных статей без vk_posted_at. '
                        'Опубликуйте черновик или укажите --post-id для такой статьи.'
                    )
                )
                return

        if post.status != 'published':
            self.stderr.write(self.style.ERROR(f'Статья {post.pk} не в статусе published'))
            return
        if post.vk_posted_at:
            self.stderr.write(
                self.style.WARNING(
                    f'Статья {post.pk} уже отмечена как ушедшая в VK (vk_posted_at задан). '
                    'send_to_vk её пропустит. Выберите другую или сбросьте vk_posted_at в админке (осторожно — дубликат на стене).'
                )
            )
            return

        title = (post.title or '')[:70]
        self.stdout.write(f'Статья id={post.pk}: {title}')
        ok = send_to_vk(post)
        post.refresh_from_db()
        if ok:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Готово. vk_posted_at={post.vk_posted_at} vk_wall_post_id={post.vk_wall_post_id}'
                )
            )
        else:
            self.stderr.write(self.style.ERROR('send_to_vk вернул False — смотрите логи Django'))
