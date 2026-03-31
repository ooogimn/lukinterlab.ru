from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from taggit.managers import TaggableManager
from ckeditor.fields import RichTextField
from ckeditor_uploader.fields import RichTextUploadingField
from mptt.models import MPTTModel, TreeForeignKey
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .telegram_utils import send_to_telegram
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

User = get_user_model()

logger = logging.getLogger(__name__)




class Post(models.Model):
    """  Модель статей для сайта """

    class PostManager(models.Manager):
        """  Кастомный менеджер для модели статей      """

        def all(self):
            """ Список статей (SQL запрос с фильтрацией для страницы списка статей)  """
            return self.get_queryset().select_related('author', 'category')

        def detail(self):
            """
            Детальная статья (SQL запрос с фильтрацией для страницы со статьёй)
            """
            return self.get_queryset() \
                .select_related('author', 'category') \
                .prefetch_related('comments', 'comments__author', 'comments__author__profile') \
                .filter(status='published')

    objects = PostManager()

    STATUS_OPTIONS = (
        ('published', 'Опубликовано'),
        ('draft', 'Черновик')
    )
    title = models.CharField(verbose_name='Заголовок', max_length=100)
    category = TreeForeignKey('Category',
                      related_name='posts',
                      on_delete=models.CASCADE, verbose_name='Категория')
    slug = models.SlugField(verbose_name='URL', max_length=255, blank=True, unique_for_date='created')
    description = models.TextField(verbose_name='ПОСТ для ТЕЛЕГРАММА', blank=True)
    content = RichTextUploadingField(verbose_name='Основной текст', blank=True)
    kartinka = models.ImageField(verbose_name='Превью поста', blank=True, null=True, upload_to='images/',)
    
    # WebP версии изображений
    image_webp = ImageSpecField(
        source='kartinka',
        processors=[ResizeToFit(1200, 800)],
        format='WEBP',
        options={'quality': 85}
    )
    
    thumbnail_webp = ImageSpecField(
        source='kartinka',
        processors=[ResizeToFill(400, 300)],
        format='WEBP',
        options={'quality': 80}
    )
    
    video = RichTextUploadingField(config_name='vstavka', verbose_name='Видео', blank=True, null=True, )
    status = models.CharField(choices=STATUS_OPTIONS, default='draft', verbose_name='Статус поста', max_length=10)
    created = models.DateTimeField(auto_now_add=True, verbose_name='Время добавления')
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата публикации',
        help_text='Заполняется при каждом переходе из черновика в «Опубликовано» (последний выход на сайт). Не путать с датой создания черновика и датой решения модератора.',
    )
    updated = models.DateTimeField(auto_now=True, verbose_name='Время обновления')
    author = models.ForeignKey(User, verbose_name='Автор', on_delete=models.CASCADE, related_name='author_posts',
                               default=1)
    updater = models.ForeignKey(User, verbose_name='Обновил', on_delete=models.SET_NULL, null=True,
                                related_name='updater_posts', blank=True)
    telegram_posted_at = models.DateTimeField(verbose_name='Время публикации в Телеге', blank=True, null=True)
    vk_posted_at = models.DateTimeField(verbose_name='Время публикации в VK', blank=True, null=True)
    vk_wall_post_id = models.PositiveIntegerField(
        verbose_name='ID поста на стене VK',
        blank=True,
        null=True,
        help_text='Из ответа wall.post (для прямой ссылки на пост в сообществе).',
    )
    fixed = models.BooleanField(verbose_name='Выполнено', default=False)
    views = models.IntegerField(verbose_name='Просмотры', default=0)
    likes_count = models.IntegerField(verbose_name='Количество лайков', default=0)
    tags = TaggableManager(blank=True)
    
    # SEO поля
    meta_title = models.CharField(verbose_name='Meta Title (до 60 символов)', max_length=60, blank=True, 
                                  help_text='Если не указано, будет использован заголовок статьи')
    meta_description = models.CharField(verbose_name='Meta Description (до 160 символов)', max_length=160, blank=True,
                                        help_text='Пустое — из описания/контента. При сохранении убирается markdown/HTML, длина обрезается до 160.')
    meta_keywords = models.TextField(verbose_name='Meta Keywords', blank=True,
                                     help_text='Через запятую. Оставьте пустым — заполнятся из тегов, контента и заголовка при сохранении.')
    og_image = models.ImageField(verbose_name='OG Image (для соцсетей)', blank=True, null=True, upload_to='seo/',
                                 help_text='Отдельное изображение для Open Graph. Если не указано, используется превью поста')
    focus_keyword = models.CharField(verbose_name='Главное ключевое слово', max_length=50, blank=True,
                                     help_text='Основное ключевое слово для SEO оптимизации')
    seo_score = models.IntegerField(verbose_name='SEO Score', default=0,
                                    help_text='Кэшированный SEO score (0-100), обновляется автоматически')
    
    # Поля для автогенерации статей
    faq_data = models.JSONField(
        verbose_name='FAQ блок (JSON)',
        blank=True,
        null=True,
        help_text='FAQ блок в формате JSON для structured data'
    )
    news_source_url = models.URLField(
        verbose_name='URL источника новостей',
        max_length=500,
        blank=True,
        null=True,
        help_text='URL статьи-источника, на основе которой создана эта статья'
    )
    parsed_content = models.TextField(
        verbose_name='Спарсенный контент из новостей',
        blank=True,
        null=True,
        help_text='Первоначальный контент (100-200 слов), спарсенный из источника новостей'
    )

    class Meta:
        db_table = 'app_posts'
        ordering = ['-updated']
        indexes = [
            models.Index(fields=['-fixed', '-created', 'status']),
            models.Index(fields=['-created', 'status']),
            models.Index(fields=['slug', 'created']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['author', '-created']),
        ]
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'

    def __str__(self):
        return self.title
    
    def has_image(self):
        """Проверка наличия файла изображения"""
        return bool(self.kartinka and hasattr(self.kartinka, 'url'))

    def get_vk_wall_url(self):
        """Прямая ссылка на пост на стене сообщества (если известен vk_wall_post_id)."""
        if not self.vk_wall_post_id:
            return None
        try:
            from django.conf import settings
            gid = str(getattr(settings, 'VK_GROUP_ID', '') or '').strip().lstrip('-')
            if not gid:
                return None
            return f'https://vk.com/wall-{gid}_{self.vk_wall_post_id}'
        except Exception:
            return None

    @property
    def vk_wall_url(self):
        """Для шаблонов: {{ post.vk_wall_url }}."""
        return self.get_vk_wall_url()

    def get_absolute_url(self):
        """Метод получения URL-адреса объекта"""
        # Если slug пустой, генерируем его из заголовка (на случай если сигнал не сработал)
        if not self.slug and self.title:
            from django.utils.text import slugify
            from django.utils import timezone
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = f'post-{self.id}'
            
            # Проверяем уникальность
            original_slug = base_slug
            counter = 1
            created_date = self.created.date() if self.created else timezone.now().date()
            
            while Post.objects.filter(
                slug=base_slug,
                created__date=created_date
            ).exclude(pk=self.pk).exists():
                base_slug = f"{original_slug}-{counter}"
                counter += 1
                if counter > 100:
                    base_slug = f"{original_slug}-{self.id}"
                    break
            
            # Сохраняем slug
            self.slug = base_slug
            Post.objects.filter(pk=self.pk).update(slug=base_slug)
        
        # Если slug всё ещё пустой, используем дефолтный
        if not self.slug:
            self.slug = f'post-{self.id}'
            Post.objects.filter(pk=self.pk).update(slug=self.slug)
        
        return reverse('Blog:post_detail', args=[self.id, self.slug])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__kartinka = self.kartinka if self.pk else None


class Category(MPTTModel):
    """ Модель категорий с вложенностью """
    kartinka_cat = models.FileField(
        verbose_name='картинка телеграмма',
        blank=True,
        upload_to='Telega/',
    )
    title = models.CharField(max_length=355, verbose_name='Название категории')
    slug = models.SlugField(max_length=255, verbose_name='URL категории', blank=True, unique=True)
    chat_id = models.CharField(verbose_name='id канала', max_length=100, null=True, blank=True)
    chat_url = models.CharField(verbose_name='url канала', max_length=100, null=True, blank=True)
    chat = models.CharField(verbose_name='канал', max_length=100, null=True, blank=True)
    description_chat = models.TextField(verbose_name='Описание канала', max_length=500, null=True, blank=True)
    description = models.TextField(verbose_name='Описание категории', max_length=500, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name='Время добавления', null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, verbose_name='Время обновления', null=True, blank=True)
    activ = models.BooleanField(verbose_name='Активно', default=False)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                            db_index=True,
                            related_name='children',
                            verbose_name='Родительская категория'
                            )
    
    class MPTTMeta:
        """Сортировка по вложенности"""
        order_insertion_by = ('title',)

    class Meta:
        """Сортировка, название модели в админ панели, таблица в данными"""
        ordering = ['title']
        indexes = [models.Index(fields=['title'])]
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        db_table = 'app_categories'
    
   
    def __str__(self):
        """Возвращение заголовка статьи"""
        return self.title

    def get_absolute_url(self):
        return reverse('Blog:post_list_by_category',
                       args=[self.slug])  # args=[self.slug]) kwargs={'slug': self.slug})


class Comment(MPTTModel):
    """Модель комментариев с поддержкой ответов"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, verbose_name='Статья', related_name='comments')
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                            db_index=True, related_name='children', verbose_name='Родительский комментарий')
    
    # MPTT поля с значениями по умолчанию
    level = models.PositiveIntegerField(default=0, editable=False)
    lft = models.PositiveIntegerField(default=0, editable=False)
    rght = models.PositiveIntegerField(default=0, editable=False)
    tree_id = models.PositiveIntegerField(default=0, editable=False)
    
    author_comment = models.CharField(max_length=80, verbose_name='Автор комментария')
    content = models.TextField(verbose_name='Текст комментария', max_length=3000)
    email = models.EmailField()
    created = models.DateTimeField(verbose_name='Время добавления', auto_now_add=True)
    updated = models.DateTimeField(verbose_name='Время обновления', auto_now=True)
    active = models.BooleanField(default=True)
    
    # Модерация
    is_admin_reply = models.BooleanField(default=False, verbose_name='Ответ администратора')

    class MPTTMeta:
        order_insertion_by = ['created']

    class Meta:
        db_table = 'app_comments'
        indexes = [models.Index(fields=['-created', 'updated', 'active'])]
        ordering = ['-created']
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'

    def __str__(self):
        return 'Комментарий от {} на {}'.format(self.author_comment, self.post)

    def get_absolute_url(self):
        return f"{self.post.get_absolute_url()}#comment-{self.id}"


class PostLike(models.Model):
    """Модель для хранения лайков статей"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes', verbose_name='Статья')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes', verbose_name='Пользователь', null=True, blank=True)
    ip_address = models.GenericIPAddressField(verbose_name='IP адрес', null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name='Время создания')
    
    class Meta:
        db_table = 'app_post_likes'
        indexes = [
            models.Index(fields=['post', 'user']),
            models.Index(fields=['post', 'ip_address']),
        ]
        verbose_name = 'Лайк статьи'
        verbose_name_plural = 'Лайки статей'
    
    def __str__(self):
        user_str = self.user.username if self.user else self.ip_address
        return f'Лайк от {user_str} на {self.post.title}'
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.user and not self.ip_address:
            raise ValidationError('Необходимо указать либо пользователя, либо IP адрес')
        if self.user and self.ip_address:
            raise ValidationError('Нельзя указывать одновременно пользователя и IP адрес')


class PostFAQ(models.Model):
    """Модель FAQ для статей (для микроразметки FAQPage)"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='faqs', verbose_name='Статья')
    question = models.CharField(max_length=255, verbose_name='Вопрос')
    answer = models.TextField(verbose_name='Ответ')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    
    class Meta:
        db_table = 'app_post_faqs'
        ordering = ['order', 'created']
        verbose_name = 'FAQ для статьи'
        verbose_name_plural = 'FAQ для статей'
        indexes = [
            models.Index(fields=['post', 'order']),
        ]
    
    def __str__(self):
        return f'FAQ: {self.question[:50]}...'


@receiver(post_save, sender=Post)
def publish_to_social(sender, instance, created, **kwargs):
    """
    Обработчик сигналов для публикации сообщений в социальных сетях при их публикации
    """
    if instance.status == 'published':
        if not instance.telegram_posted_at:
            send_to_telegram(instance)
        if not instance.vk_posted_at:
            post_pk = instance.pk

            def _enqueue_vk():
                try:
                    from django_q.tasks import async_task

                    async_task('Blog.vk_utils.send_to_vk_by_id', post_pk)
                except Exception:
                    logger.exception('VK: не удалось поставить задачу в очередь django-q')

            transaction.on_commit(_enqueue_vk)

