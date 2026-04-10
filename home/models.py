from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from mptt.models import MPTTModel, TreeForeignKey
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit
from ckeditor_uploader.fields import RichTextUploadingField

class Otziv(models.Model):
    class OtzivManager(models.Manager):
        """  Кастомный менеджер для модели статей      """
        def all(self):
            """ Список статей (SQL запрос с фильтрацией для страницы списка статей)  """
            return self.get_queryset()

    objects = OtzivManager()

    name= models.CharField(verbose_name="Имя",max_length=250, blank=True)
    firma = models.CharField(verbose_name="Компания",max_length=250, blank=True)
    foto = models.FileField(verbose_name="Ваше фото",upload_to='otzivs', blank=True)
    
    # WebP версия фото
    foto_webp = ImageSpecField(
        source='foto',
        processors=[ResizeToFill(150, 150)],
        format='WEBP',
        options={'quality': 85}
    )
    
    body = models.TextField(verbose_name="Текст отзыва", blank=True)
    created = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    save_on_top = True

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['-created', 'active']),
        ]
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('home:otzivs')


class OtzivComment(MPTTModel):
    """Модель комментариев к отзывам с возможностью ответов"""
    
    otziv = models.ForeignKey(Otziv, on_delete=models.CASCADE, verbose_name='Отзыв', related_name='comments')
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                            db_index=True, related_name='children', verbose_name='Родительский комментарий')
    
    # Информация о комментаторе
    author_name = models.CharField(max_length=80, verbose_name='Имя автора')
    author_email = models.EmailField(verbose_name='Email автора')
    author_company = models.CharField(max_length=200, verbose_name='Компания', blank=True)
    
    # Содержание комментария
    content = models.TextField(verbose_name='Текст комментария', max_length=3000)
    
    # Метаданные
    created = models.DateTimeField(verbose_name='Время добавления', auto_now_add=True)
    updated = models.DateTimeField(verbose_name='Время обновления', auto_now=True)
    active = models.BooleanField(default=True, verbose_name='Активен')
    
    # Модерация
    is_admin_reply = models.BooleanField(default=False, verbose_name='Ответ администратора')
    
    class MPTTMeta:
        order_insertion_by = ['created']

    class Meta:
        db_table = 'otziv_comments'
        indexes = [models.Index(fields=['-created', 'updated', 'active'])]
        ordering = ['-created']
        verbose_name = 'Комментарий к отзыву'
        verbose_name_plural = 'Комментарии к отзывам'

    def __str__(self):
        return f'Комментарий от {self.author_name} к отзыву {self.otziv.name}'

    def get_absolute_url(self):
        return f"{self.otziv.get_absolute_url()}#comment-{self.id}"


class Rabota(models.Model):
    CATEGORY_CHOICES = [
        ('website', 'Сайт'),
        ('bot', 'Бот'),
        ('app', 'Приложение'),
        ('shop', 'Магазин'),
        ('other', 'Другое'),
    ]
    
    STATUS_CHOICES = [
        ('completed', 'Завершен'),
        ('in_progress', 'В разработке'),
        ('maintenance', 'На поддержке'),
    ]
    
    class RabotaManager(models.Manager):
        """  Кастомный менеджер для модели работ      """
        def all(self):
            """ Список работ (SQL запрос с фильтрацией для страницы списка работ)  """
            return self.get_queryset().filter(is_visible=True)

    objects = RabotaManager()

    is_visible = models.BooleanField(default=True, verbose_name='Отображать на сайте',
                                     help_text='Снимите галку, чтобы скрыть проект с сайта')

    name = models.CharField(max_length=200, verbose_name='Название проекта')
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='website', 
        verbose_name='Категория'
    )
    image = models.ImageField(
        upload_to='rabotas', 
        blank=True, 
        verbose_name='Скриншот проекта',
        help_text='Рекомендуемый размер: 800x600px'
    )
    
    # WebP версии
    image_webp = ImageSpecField(
        source='image',
        processors=[ResizeToFit(800, 600)],
        format='WEBP',
        options={'quality': 85}
    )
    
    thumbnail_webp = ImageSpecField(
        source='image',
        processors=[ResizeToFill(400, 300)],
        format='WEBP',
        options={'quality': 80}
    )
    
    adres = models.URLField(
        max_length=500, 
        blank=True, 
        verbose_name='URL проекта',
        help_text='Ссылка на живой проект'
    )
    body = models.TextField(
        default="Современный веб-сайт на Python Django с адаптивным дизайном",
        blank=True, 
        verbose_name='Описание проекта'
    )
    technologies = models.TextField(
        blank=True, 
        verbose_name='Использованные технологии',
        help_text='Python, Django, React, PostgreSQL и т.д.'
    )
    history_text = RichTextUploadingField(blank=True, verbose_name='История развития', help_text='Описание процесса создания и развития проекта')
    resources_text = RichTextUploadingField(blank=True, verbose_name='Ресурсы', help_text='Список использованных ресурсов (команда, время, ассеты)')
    parameters_text = RichTextUploadingField(blank=True, verbose_name='Технические параметры', help_text='Спецификации, архитектура, нагрузки')
    instructions_text = RichTextUploadingField(blank=True, verbose_name='Инструкции', help_text='Руководство пользователя или примеры использования')
    tariffs_text = RichTextUploadingField(blank=True, verbose_name='Тарифы', help_text='Стоимость разработки или тарифные планы')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='completed', 
        verbose_name='Статус проекта'
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    featured = models.BooleanField(default=False, verbose_name='Рекомендуемый проект')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    
    # Связь с услугой (воронка продаж)
    related_service = models.ForeignKey('Service', on_delete=models.SET_NULL, null=True, blank=True, related_name='portfolio_rabotas', verbose_name='Связанная услуга/тариф')
    
    # SEO поля
    meta_title = models.CharField("Meta Title", max_length=255, blank=True, help_text="Заголовок для поисковиков")
    meta_description = models.TextField("Meta Description", max_length=500, blank=True, help_text="Описание для поисковиков")
    meta_keywords = models.CharField("Meta Keywords", max_length=500, blank=True, help_text="Ключевые слова через запятую")
    focus_keyword = models.CharField("Focus Keyword", max_length=100, blank=True, help_text="Основное ключевое слово")
    seo_score = models.IntegerField("SEO Score", default=0, help_text="Оценка оптимизации (0-100)")

    class Meta:
        ordering = ['order', '-created']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['status']),
            models.Index(fields=['featured']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['-created', 'status']),
        ]
        verbose_name = 'Работа'
        verbose_name_plural = 'Работы'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('home:rabota', args=[self.id])
    
    def get_category_display_name(self):
        """Возвращает красивое название категории"""
        return dict(self.CATEGORY_CHOICES)[self.category]
    
    def get_status_display_name(self):
        """Возвращает красивое название статуса"""
        return dict(self.STATUS_CHOICES)[self.status]
    
    def get_image_url_with_version(self):
        """Возвращает URL изображения с версией для обхода кэша браузера"""
        if self.image:
            # Добавляем timestamp обновления для обхода кэша
            version = int(self.updated.timestamp()) if self.updated else ''
            return f"{self.image.url}?v={version}"
        return None
    
    def get_thumbnail_webp_url_with_version(self):
        """Возвращает URL WebP миниатюры с версией для обхода кэша браузера"""
        if self.thumbnail_webp:
            # Добавляем timestamp обновления для обхода кэша
            version = int(self.updated.timestamp()) if self.updated else ''
            return f"{self.thumbnail_webp.url}?v={version}"
        return None


class RabotaMedia(models.Model):
    """Модель для галереи изображений и видео портфолио"""
    rabota = models.ForeignKey(Rabota, on_delete=models.CASCADE, related_name='media_items', verbose_name='Проект')
    file = models.FileField(upload_to='rabota_media/', verbose_name='Файл (Изображение или Видео)')
    is_video = models.BooleanField(default=False, verbose_name='Это видео')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created']
        verbose_name = 'Медиафайл проекта'
        verbose_name_plural = 'Медиафайлы проекта'
        
    def __str__(self):
        return f"Медиа для {self.rabota.name} ({self.id})"
        
    def save(self, *args, **kwargs):
        # Auto-detect if it's a video based on extension
        if self.file and hasattr(self.file, 'name') and self.file.name:
            ext = self.file.name.split('.')[-1].lower()
            if ext in ['mp4', 'webm', 'ogg', 'mov', 'avi']:
                self.is_video = True
            else:
                self.is_video = False
        super().save(*args, **kwargs)




class ContactMessage(models.Model):
    """Модель для сохранения сообщений из формы контактов"""
    name = models.CharField(max_length=100, verbose_name="Имя")
    email = models.EmailField(verbose_name="Email")
    message = models.TextField(verbose_name="Сообщение")
    attachment = models.FileField(upload_to='contact_attachments/', blank=True, null=True, verbose_name="Вложение")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP адрес")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    is_spam = models.BooleanField(default=False, verbose_name="Спам")
    
    class Meta:
        verbose_name = "Сообщение контактов"
        verbose_name_plural = "Сообщения контактов"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['-created', 'is_read']),
            models.Index(fields=['email', 'created']),
            models.Index(fields=['ip_address', '-created']),
        ]
    
    def __str__(self):
        return f"Сообщение от {self.name} ({self.email})"
    
    def get_attachment_filename(self):
        """Возвращает имя файла вложения"""
        if self.attachment:
            return self.attachment.name.split('/')[-1]
        return None


class SEOModel(models.Model):
    """SEO модель для управления мета-тегами"""
    page_url = models.CharField(max_length=200, unique=True, verbose_name="URL страницы")
    title = models.CharField(max_length=200, verbose_name="Title (meta / до ~60 знаков в выдаче)")
    description = models.CharField(
        max_length=512, verbose_name="Description (meta, в выдаче режется ~160 знаков)"
    )
    keywords = models.TextField(blank=True, verbose_name="Keywords")
    og_title = models.CharField(max_length=200, blank=True, verbose_name="OG Title")
    og_description = models.CharField(max_length=512, blank=True, verbose_name="OG Description")
    og_image = models.ImageField(upload_to='seo/', blank=True, verbose_name="OG Image")
    canonical_url = models.URLField(blank=True, verbose_name="Canonical URL")
    h1 = models.CharField(max_length=100, blank=True, verbose_name="H1 заголовок")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "SEO настройки"
        verbose_name_plural = "SEO настройки"
        ordering = ['page_url']
        indexes = [
            models.Index(fields=['page_url']),
        ]
    
    def __str__(self):
        return f"SEO: {self.page_url}"
    
    def get_og_title(self):
        return self.og_title or self.title
    
    def get_og_description(self):
        return self.og_description or self.description


class SectionBackground(models.Model):
    """Модель для управления фоновыми видео/фото секций"""
    
    SECTION_CHOICES = [
        ('home', 'Главная секция'),
        ('about', 'О нас'),
        ('resume', 'Услуги'),
        ('portfolio', 'Портфолио'),
        ('testimonials', 'Отзывы'),
        ('blog', 'Блог'),
        ('contact', 'Контакты'),
    ]
    
    BACKGROUND_TYPE_CHOICES = [
        ('image', 'Изображение'),
        ('video', 'Видео'),
        ('gradient', 'Градиент'),
    ]
    
    section = models.CharField(
        max_length=20, 
        choices=SECTION_CHOICES, 
        unique=True,
        verbose_name='Секция'
    )
    
    background_type = models.CharField(
        max_length=10,
        choices=BACKGROUND_TYPE_CHOICES,
        default='image',
        verbose_name='Тип фона'
    )
    
    # Для изображений
    background_image = models.ImageField(
        upload_to='section_backgrounds/',
        blank=True,
        null=True,
        verbose_name='Фоновое изображение',
        help_text='Рекомендуемый размер: 1920x1080px'
    )
    
    # Для видео
    background_video = models.FileField(
        upload_to='section_backgrounds/videos/',
        blank=True,
        null=True,
        verbose_name='Фоновое видео',
        help_text='Формат: MP4, WebM. Размер: до 50MB'
    )
    
    # Для градиентов
    gradient_start = models.CharField(
        max_length=7,
        default='#3b82f6',
        verbose_name='Начальный цвет градиента',
        help_text='Формат: #RRGGBB'
    )
    
    gradient_end = models.CharField(
        max_length=7,
        default='#8b5cf6',
        verbose_name='Конечный цвет градиента',
        help_text='Формат: #RRGGBB'
    )
    
    gradient_direction = models.CharField(
        max_length=20,
        default='to-br',
        choices=[
            ('to-r', 'Вправо'),
            ('to-l', 'Влево'),
            ('to-t', 'Вверх'),
            ('to-b', 'Вниз'),
            ('to-tr', 'Вправо-вверх'),
            ('to-tl', 'Влево-вверх'),
            ('to-br', 'Вправо-вниз'),
            ('to-bl', 'Влево-вниз'),
        ],
        verbose_name='Направление градиента'
    )
    
    # Общие настройки
    overlay_opacity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Прозрачность наложения',
        help_text='0-100, где 0 - без наложения, 100 - полностью темный'
    )
    
    overlay_color = models.CharField(
        max_length=7,
        default='#000000',
        verbose_name='Цвет наложения',
        help_text='Формат: #RRGGBB'
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    
    created = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    
    class Meta:
        verbose_name = 'Фон секции'
        verbose_name_plural = 'Фоны секций'
        ordering = ['section']
    
    def __str__(self):
        return f"Фон секции: {self.get_section_display()}"
    
    def get_background_style(self):
        """Возвращает CSS стили для фона"""
        if not self.is_active:
            return ""
        
        if self.background_type == 'image' and self.background_image:
            return f"background-image: url('{self.background_image.url}'); background-size: cover; background-position: center; background-repeat: no-repeat;"
        
        elif self.background_type == 'gradient':
            return f"background: linear-gradient({self.gradient_direction}, {self.gradient_start}, {self.gradient_end});"
        
        return ""
    
    def get_overlay_style(self):
        """Возвращает CSS стили для наложения"""
        if self.overlay_opacity > 0:
            opacity = self.overlay_opacity / 100
            return f"background-color: {self.overlay_color}; opacity: {opacity};"
        return ""
    
    def get_video_url(self):
        """Возвращает URL видео"""
        if self.background_type == 'video' and self.background_video:
            return self.background_video.url
        return None


class Service(models.Model):
    """Модель для основных услуг"""
    title = models.CharField("Название услуги", max_length=200)
    description = models.TextField("Описание", blank=True)
    icon = models.ImageField("Иконка/картинка", upload_to="services/", blank=True, null=True)
    price = models.CharField("Цена (текст)", max_length=50, blank=True, help_text="Например: от 50,000 ₽. Если заполнено числовое поле ниже, это поле будет игнорироваться.")
    price_value = models.DecimalField("Цена (число)", max_digits=12, decimal_places=2, null=True, blank=True, help_text="Числовое значение для расчетов.")
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активно", default=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['order']
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        indexes = [
            models.Index(fields=['is_active', 'order']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.title

    def get_display_price(self):
        """Возвращает отформатированную цену из числа или текста"""
        if self.price_value:
            formatted = "{:,}".format(int(self.price_value)).replace(',', ' ')
            return f"от {formatted} ₽"
        
        price_str = self.price.strip()
        if not price_str:
            return ""
        if price_str.lower().startswith('от'):
            return price_str
        return f"от {price_str}"

    def get_absolute_url(self):
        return reverse('home:service-detail', args=[self.id])


class ExtraService(models.Model):
    """Модель для дополнительных услуг в составе основной услуги"""
    service = models.ForeignKey(Service, related_name="extra_services", on_delete=models.CASCADE, verbose_name="Основная услуга")
    title = models.CharField("Название доп. услуги", max_length=200)
    description = models.TextField("Описание", blank=True)
    price = models.CharField("Цена (текст)", max_length=50, blank=True, help_text="Например: от 15,000 ₽/мес")
    price_value = models.DecimalField("Цена (число)", max_digits=12, decimal_places=2, null=True, blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активно", default=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['order']
        verbose_name = "Дополнительная услуга в составе"
        verbose_name_plural = "Дополнительные услуги в составе"
        db_table = 'home_service_extraservice'

    def __str__(self):
        return f"{self.title} ({self.service.title})"

    def get_display_price(self):
        if self.price_value:
            formatted = "{:,}".format(int(self.price_value)).replace(',', ' ')
            return f"от {formatted} ₽"
        
        price_str = self.price.strip()
        if not price_str:
            return ""
        if price_str.lower().startswith('от'):
            return price_str
        return f"от {price_str}"


class StandaloneExtraService(models.Model):
    """Модель для независимых дополнительных услуг"""
    title = models.CharField("Название услуги", max_length=200)
    description = models.TextField("Описание", blank=True)
    price = models.CharField("Цена (текст)", max_length=50, blank=True, help_text="Например: от 15,000 ₽/мес")
    price_value = models.DecimalField("Цена (число)", max_digits=12, decimal_places=2, null=True, blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активно", default=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['order']
        verbose_name = "Дополнительная услуга"
        verbose_name_plural = "Дополнительные услуги"
        db_table = 'home_standalone_extraservice'
        indexes = [
            models.Index(fields=['is_active', 'order']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.title

    def get_display_price(self):
        if self.price_value:
            formatted = "{:,}".format(int(self.price_value)).replace(',', ' ')
            return f"от {formatted} ₽"
        
        price_str = self.price.strip()
        if not price_str:
            return ""
        if price_str.lower().startswith('от'):
            return price_str
        return f"от {price_str}"


class Cart(models.Model):
    """Модель корзины заказа"""
    session_key = models.CharField("Ключ сессии", max_length=40, unique=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

    def __str__(self):
        return f"Корзина {self.session_key}"

    def get_total_price(self):
        """Получить общую стоимость корзины"""
        return sum(item.get_total_price() for item in self.items.all())

    def get_items_count(self):
        """Получить количество товаров в корзине"""
        return self.items.count()


class CartItem(models.Model):
    """Модель элемента корзины"""
    SERVICE_TYPE_CHOICES = [
        ('service', 'Основная услуга'),
        ('extra_service', 'Дополнительная услуга'),
    ]

    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE, verbose_name="Корзина")
    service_type = models.CharField("Тип услуги", max_length=20, choices=SERVICE_TYPE_CHOICES)
    service_id = models.PositiveIntegerField("ID услуги")
    title = models.CharField("Название услуги", max_length=200)
    price = models.CharField("Цена", max_length=50)
    price_value = models.DecimalField("Цена (число)", max_digits=12, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField("Количество", default=1)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"
        unique_together = ['cart', 'service_type', 'service_id']

    def __str__(self):
        return f"{self.title} (x{self.quantity})"

    def get_total_price(self):
        """Получить общую стоимость элемента"""
        if self.price_value:
            return self.price_value * self.quantity
            
        # Извлекаем числовое значение из строки цены (fallback)
        price_str = self.price.replace('₽', '').replace(',', '').replace('от', '').replace(' ', '')
        try:
            return float(price_str) * self.quantity
        except ValueError:
            return 0


class Customer(models.Model):
    """Модель заказчика для личного кабинета"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Пользователь", null=True, blank=True)
    avatar = models.ImageField(
        "Аватар",
        upload_to="customer_avatars/",
        blank=True,
        null=True,
        help_text="Отображается в шапке сайта и в кабинете (рекомендуем квадрат, до 2 МБ).",
    )
    phone = models.CharField("Телефон", max_length=20, blank=True)
    company = models.CharField("Компания", max_length=200, blank=True)
    position = models.CharField("Должность", max_length=100, blank=True)
    address = models.TextField("Адрес", blank=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    is_active = models.BooleanField("Активен", default=True)
    
    class Meta:
        verbose_name = "Заказчик"
        verbose_name_plural = "Заказчики"
        ordering = ['-created']
    
    def __str__(self):
        if self.user:
            return f"{self.user.get_full_name() or self.user.username}"
        return f"Заказчик {self.id}"
    
    def get_full_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return f"Заказчик {self.id}"
    
    def get_email(self):
        if self.user:
            return self.user.email
        return ""


class OrderComment(models.Model):
    """Модель комментариев к заказу"""
    order = models.ForeignKey('Order', related_name='comments', on_delete=models.CASCADE, verbose_name="Заказ")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор")
    content = models.TextField("Комментарий", max_length=2000)
    is_admin_comment = models.BooleanField("Комментарий администратора", default=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Комментарий к заказу"
        verbose_name_plural = "Комментарии к заказам"
        ordering = ['-created']
    
    def __str__(self):
        return f"Комментарий к заказу {self.order.order_number} от {self.author.username}"


class Order(models.Model):
    """Модель заказа"""
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('processing', 'В обработке'),
        ('confirmed', 'Подтвержден'),
        ('in_progress', 'В работе'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачен'),
        ('failed', 'Ошибка оплаты'),
    ]

    order_number = models.CharField("Номер заказа", max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Заказчик", null=True, blank=True)
    customer_name = models.CharField("Имя клиента", max_length=100)
    customer_email = models.EmailField("Email клиента")
    customer_phone = models.CharField("Телефон клиента", max_length=20)
    total_price = models.DecimalField("Общая стоимость", max_digits=10, decimal_places=2)
    status = models.CharField("Статус заказа", max_length=20, choices=STATUS_CHOICES, default='new')
    payment_status = models.CharField("Статус оплаты", max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_id = models.CharField("ID платежа YooKassa", max_length=100, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['-created']
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['customer', '-created']),
            models.Index(fields=['payment_status', 'status']),
            models.Index(fields=['-created']),
            models.Index(fields=['payment_id']),
        ]

    def __str__(self):
        return f"Заказ {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Генерируем номер заказа
            last_order = Order.objects.order_by('-id').first()
            if last_order:
                last_number = int(last_order.order_number[3:])  # Убираем "ORD"
                self.order_number = f"ORD{last_number + 1:06d}"
            else:
                self.order_number = "ORD000001"
        super().save(*args, **kwargs)
    
    def get_status_display_class(self):
        """Возвращает CSS класс для статуса"""
        status_classes = {
            'new': 'bg-blue-100 text-blue-800',
            'processing': 'bg-yellow-100 text-yellow-800',
            'confirmed': 'bg-green-100 text-green-800',
            'in_progress': 'bg-purple-100 text-purple-800',
            'completed': 'bg-green-100 text-green-800',
            'cancelled': 'bg-red-100 text-red-800',
        }
        return status_classes.get(self.status, 'bg-gray-100 text-gray-800')
    
    def get_payment_status_display_class(self):
        """Возвращает CSS класс для статуса оплаты"""
        payment_classes = {
            'pending': 'bg-yellow-100 text-yellow-800',
            'paid': 'bg-green-100 text-green-800',
            'failed': 'bg-red-100 text-red-800',
        }
        return payment_classes.get(self.payment_status, 'bg-gray-100 text-gray-800')


class OrderItem(models.Model):
    """Модель элемента заказа"""
    SERVICE_TYPE_CHOICES = [
        ('service', 'Основная услуга'),
        ('extra_service', 'Дополнительная услуга'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="Заказ")
    service_type = models.CharField("Тип услуги", max_length=20, choices=SERVICE_TYPE_CHOICES)
    service_id = models.PositiveIntegerField("ID услуги")
    title = models.CharField("Название услуги", max_length=200)
    price = models.CharField("Цена", max_length=50)
    price_value = models.DecimalField("Цена (число)", max_digits=12, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"

    def __str__(self):
        return f"{self.title} (x{self.quantity})"
    
    def get_total_price(self):
        """Получить общую стоимость элемента"""
        if self.price_value:
            return self.price_value * self.quantity
            
        # Извлекаем числовое значение из строки цены (fallback)
        price_str = self.price.replace('₽', '').replace(',', '').replace('от', '').replace(' ', '')
        try:
            return float(price_str) * self.quantity
        except ValueError:
            return 0


class OrderQuestionnaire(models.Model):
    """Модель опросного листа заказа"""
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='questionnaire', verbose_name="Заказ")
    
    # Основная информация о проекте
    project_name = models.CharField("Название проекта", max_length=200, blank=True)
    project_description = models.TextField("Описание проекта", blank=True)
    target_audience = models.TextField("Целевая аудитория", blank=True)
    competitors = models.TextField("Конкуренты", blank=True)
    
    # Технические требования
    technical_requirements = models.TextField("Технические требования", blank=True)
    design_preferences = models.TextField("Предпочтения по дизайну", blank=True)
    functionality_requirements = models.TextField("Требования к функциональности", blank=True)
    
    # Сроки и бюджет
    deadline = models.DateField("Желаемый срок сдачи", null=True, blank=True)
    budget_range = models.CharField("Диапазон бюджета", max_length=100, blank=True)
    
    # Дополнительные требования и пожелания
    additional_requirements = models.TextField("Дополнительные требования и пожелания", blank=True)
    
    # Контактная информация
    preferred_contact_method = models.CharField("Предпочтительный способ связи", max_length=50, blank=True)
    additional_contacts = models.TextField("Дополнительные контакты", blank=True)
    
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Опросный лист"
        verbose_name_plural = "Опросные листы"

    def __str__(self):
        return f"Опросный лист заказа {self.order.order_number}"


class OrderFile(models.Model):
    """Модель для файлов заказа"""
    order = models.ForeignKey(Order, related_name='files', on_delete=models.CASCADE, verbose_name="Заказ")
    file = models.FileField("Файл", upload_to='order_files/%Y/%m/%d/', blank=True, null=True)
    filename = models.CharField("Название файла", max_length=255, blank=True)
    description = models.CharField("Описание файла", max_length=500, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    class Meta:
        verbose_name = "Файл заказа"
        verbose_name_plural = "Файлы заказов"

    def __str__(self):
        return f"{self.filename} (заказ {self.order.order_number})"


class CookieConsent(models.Model):
    """Модель для хранения согласия пользователя на использование cookie"""
    session_key = models.CharField(max_length=40, unique=True, verbose_name="Ключ сессии")
    ip_address = models.GenericIPAddressField(verbose_name="IP адрес", null=True, blank=True)
    
    # Типы согласия
    essential_cookies = models.BooleanField(default=True, verbose_name="Обязательные cookie")
    analytics_cookies = models.BooleanField(default=False, verbose_name="Аналитические cookie")
    marketing_cookies = models.BooleanField(default=False, verbose_name="Маркетинговые cookie")
    
    consent_given = models.BooleanField(default=False, verbose_name="Согласие дано")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Согласие на cookie"
        verbose_name_plural = "Согласия на cookie"
        ordering = ['-created']
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['ip_address', '-created']),
        ]
    
    def __str__(self):
        return f"Cookie consent {self.session_key}"


class LegalInfo(models.Model):
    """Модель для правовой информации о компании"""
    
    # Основная информация о компании
    company_name = models.CharField("Название компании", max_length=255, default="ООО \"ЛукИнтерЛаб\"")
    company_full_name = models.CharField("Полное наименование", max_length=500, default="Общество с ограниченной ответственностью \"ЛукИнтерЛаб\"")
    inn = models.CharField("ИНН", max_length=12, blank=True)
    kpp = models.CharField("КПП", max_length=9, blank=True)
    ogrn = models.CharField("ОГРН", max_length=15, blank=True)
    
    # Адрес
    legal_address = models.TextField("Юридический адрес", blank=True, default="г. Москва, ул. Ярославская, д. 9")
    actual_address = models.TextField("Фактический адрес", blank=True)
    
    # Контакты
    phone = models.CharField("Телефон", max_length=50, default="+7-905-856-02-82")
    email = models.CharField("Email", max_length=100, default="Ya@LukyanovSY.ru")
    website = models.URLField("Сайт", default="https://lukinterlab.ru")
    
    # Банковские реквизиты
    bank_name = models.CharField("Название банка", max_length=255, blank=True)
    bank_account = models.CharField("Расчётный счёт", max_length=20, blank=True)
    correspondent_account = models.CharField("Корреспондентский счёт", max_length=20, blank=True)
    bik = models.CharField("БИК", max_length=9, blank=True)
    
    # Документы (файлы)
    contract_file = models.FileField("Договор", upload_to='legal_docs/', blank=True, null=True)
    extract_file = models.FileField("Выписка из ЕГРЮЛ", upload_to='legal_docs/', blank=True, null=True)
    certificate_file = models.FileField("Сертификат Минцифры", upload_to='legal_docs/', blank=True, null=True)
    
    # Дополнительная информация
    about_site = models.TextField("О сайте", blank=True, help_text="Информация о сайте и его назначении")
    about_company = models.TextField("О компании", blank=True, help_text="Подробная информация о компании")
    terms_of_use = models.TextField("Условия использования", blank=True)
    privacy_policy = models.TextField("Политика конфиденциальности", blank=True)
    
    # Метаданные
    is_active = models.BooleanField("Активна", default=True)
    created = models.DateTimeField("Дата создания", auto_now_add=True)
    updated = models.DateTimeField("Дата обновления", auto_now=True)
    
    class Meta:
        verbose_name = "Правовая информация"
        verbose_name_plural = "Правовая информация"
        ordering = ['-updated']
    
    def __str__(self):
        return f"Правовая информация - {self.company_name}"
    
    def save(self, *args, **kwargs):
        # Убеждаемся, что есть только одна активная запись
        if self.is_active:
            LegalInfo.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class SiteMarketingSettings(models.Model):
    """
    Единые настройки: рекламные вставки (РСЯ и др.), метрики, произвольный HTML.
    Одна строка (pk=1) — правка через /manage/marketing/ или админку.
    """

    yandex_rsya_html = models.TextField(
        'HTML блоков РСЯ / медийной рекламы',
        blank=True,
        help_text='Вставьте код рекламных блоков (например, из кабинета Яндекса). Выводится в зоне reclama (подключается на всех страницах с base.html).',
    )
    yandex_metrika_html = models.TextField(
        'Яндекс.Метрика и счётчики (фрагмент для &lt;head&gt; или полный)',
        blank=True,
        help_text='Если заполнено и включена подмена — выводится вместо встроенного счётчика в шаблоне.',
    )
    google_tag_head_html = models.TextField(
        'Google Tag Manager / аналитика (часть для &lt;head&gt;)',
        blank=True,
    )
    google_tag_body_html = models.TextField(
        'Google Tag Manager (noscript сразу после &lt;body&gt;)',
        blank=True,
    )
    head_extra_html = models.TextField(
        'Дополнительно в &lt;head&gt;',
        blank=True,
        help_text='Проверка сайта, пиксели и т.п.',
    )
    body_end_html = models.TextField(
        'Перед закрытием &lt;/body&gt;',
        blank=True,
        help_text='Доп. скрипты, вторичные пиксели.',
    )
    custom_promo_banner_html = models.TextField(
        'Свой промо-блок (HTML)',
        blank=True,
        help_text='Произвольный блок: баннер, встроенное видео, текст. Рендерится |safe рядом с рекламной зоной.',
    )
    promo_image = models.ImageField(
        'Промо-картинка (опционально)',
        upload_to='marketing/',
        blank=True,
        null=True,
    )
    promo_link = models.URLField(
        'Ссылка с промо-картинки',
        blank=True,
    )
    replace_builtin_counters = models.BooleanField(
        'Заменить встроенные GTM и Метрику в шаблоне',
        default=False,
        help_text='Если включено — блоки из полей выше подставляются вместо захардкоженных скриптов в base.html (заполните Metrika/GTM вручную).',
    )
    active = models.BooleanField('Включить вывод с БД', default=True)

    class Meta:
        verbose_name = 'Реклама и метрики (сайт)'
        verbose_name_plural = 'Реклама и метрики (сайт)'

    def __str__(self):
        return 'Настройки рекламы и метрик'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CustomerSupportThread(models.Model):
    """Обращение клиента в поддержку (переписка — CustomerSupportMessage)."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Открыт'
        ANSWERED = 'answered', 'Есть ответ'
        CLOSED = 'closed', 'Закрыт'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='support_threads',
        verbose_name='Клиент',
    )
    subject = models.CharField('Тема', max_length=200)
    status = models.CharField(
        'Статус',
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Обращение в поддержку'
        verbose_name_plural = 'Обращения в поддержку'
        ordering = ['-updated_at']

    def __str__(self):
        return f'#{self.pk} {self.subject}'


class CustomerSupportMessage(models.Model):
    thread = models.ForeignKey(
        CustomerSupportThread,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Обращение',
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Автор')
    is_staff = models.BooleanField('Сообщение поддержки', default=False)
    body = models.TextField('Текст', max_length=8000)
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение поддержки'
        verbose_name_plural = 'Сообщения поддержки'
        ordering = ['created_at']

    def __str__(self):
        return f'#{self.pk} в треде {self.thread_id}'

