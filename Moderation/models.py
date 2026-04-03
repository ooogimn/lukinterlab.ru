from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from Blog.models import Post, Comment
import json

User = get_user_model()


class ModerationCriteria(models.Model):
    """Критерии модерации статей"""
    
    name = models.CharField(max_length=200, verbose_name='Название набора критериев')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    # Критерии в формате JSON
    criteria = models.JSONField(
        default=dict,
        verbose_name='Критерии модерации',
        help_text='JSON с критериями: min_length, max_length, required_keywords, forbidden_words, tone, structure'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Критерий модерации статей'
        verbose_name_plural = 'Критерии модерации статей'
        ordering = ['-created']
    
    def __str__(self):
        return self.name


class ArticleModeration(models.Model):
    """Модерация статей блога"""
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает модерации'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('needs_revision', 'Требует доработки'),
    ]
    
    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name='moderation',
        verbose_name='Статья'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Статус модерации'
    )
    
    moderator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_articles',
        verbose_name='Модератор'
    )
    
    criteria_used = models.ForeignKey(
        ModerationCriteria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Использованные критерии'
    )
    
    # Результаты проверки
    check_results = models.JSONField(
        default=dict,
        verbose_name='Результаты проверки',
        help_text='Детальные результаты проверки по каждому критерию'
    )
    
    # Комментарии модератора
    moderator_comment = models.TextField(
        blank=True,
        verbose_name='Комментарий модератора'
    )
    
    # Временные метки
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено на модерацию')
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name='Промодерировано')
    
    class Meta:
        verbose_name = 'Модерация статьи'
        verbose_name_plural = 'Модерация статей'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['moderator', '-moderated_at']),
        ]
    
    def __str__(self):
        return f"Модерация: {self.post.title} ({self.get_status_display()})"


class CommentModerationCriteria(models.Model):
    """Критерии модерации комментариев"""
    
    name = models.CharField(max_length=200, verbose_name='Название набора критериев')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    # Критерии в формате JSON
    criteria = models.JSONField(
        default=dict,
        verbose_name='Критерии модерации',
        help_text='JSON с критериями: forbidden_words, min_length, max_length, spam_patterns, tone_rules'
    )
    
    # Действия при нарушении
    actions = models.JSONField(
        default=dict,
        verbose_name='Действия',
        help_text='JSON с действиями: delete, correct, reply'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Критерий модерации комментариев'
        verbose_name_plural = 'Критерии модерации комментариев'
        ordering = ['-created']
    
    def __str__(self):
        return self.name


class CommentModeration(models.Model):
    """Универсальная модерация комментариев (для всех типов)"""
    
    ACTION_CHOICES = [
        ('approved', 'Одобрено'),
        ('hidden', 'Скрыто (ожидает ручной проверки)'),
        ('deleted', 'Удалено'),
        ('corrected', 'Исправлено'),
        ('replied', 'Ответ добавлен'),
    ]
    
    COMMENT_TYPES = [
        ('blog.comment', 'Комментарий к статье'),
        ('home.otzivcomment', 'Комментарий к отзыву'),
        ('home.ordercomment', 'Комментарий к заказу'),
    ]
    
    # GenericForeignKey для универсальной связи с любым типом комментария
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name='Тип комментария',
        null=True,  # Временно nullable для миграции
        blank=True
    )
    object_id = models.PositiveIntegerField(verbose_name='ID комментария', null=True, blank=True)
    comment = GenericForeignKey('content_type', 'object_id')
    
    # Тип комментария (для удобства фильтрации)
    comment_type = models.CharField(
        max_length=50,
        choices=COMMENT_TYPES,
        verbose_name='Тип комментария',
        default='blog.comment'  # По умолчанию для обратной совместимости
    )
    
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        null=True,
        blank=True,
        verbose_name='Действие'
    )
    
    criteria_used = models.ForeignKey(
        CommentModerationCriteria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Использованные критерии'
    )
    
    # Результаты проверки
    check_results = models.JSONField(
        default=dict,
        verbose_name='Результаты проверки'
    )
    
    # Исправленный текст (если было действие 'corrected')
    corrected_text = models.TextField(
        blank=True,
        verbose_name='Исправленный текст'
    )
    
    # Автоматический ответ (если было действие 'replied')
    auto_reply = models.TextField(
        blank=True,
        verbose_name='Автоматический ответ'
    )
    
    # Временные метки
    checked_at = models.DateTimeField(auto_now_add=True, verbose_name='Проверено')
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name='Промодерировано')
    
    class Meta:
        verbose_name = 'Модерация комментария'
        verbose_name_plural = 'Модерация комментариев'
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['action', '-checked_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['comment_type', '-checked_at']),
        ]
        unique_together = [['content_type', 'object_id']]
    
    def __str__(self):
        comment_id = self.object_id if self.object_id else 'unknown'
        return f"Модерация {self.get_comment_type_display()} #{comment_id} ({self.get_action_display() if self.action else 'Не обработан'})"
    
    def get_comment_author_name(self):
        """Получить имя автора комментария (универсальный метод)"""
        if not self.comment:
            return "Неизвестно"
        
        # Comment (Blog)
        if hasattr(self.comment, 'author_comment'):
            return self.comment.author_comment
        
        # OtzivComment
        if hasattr(self.comment, 'author_name'):
            return self.comment.author_name
        
        # OrderComment
        if hasattr(self.comment, 'author'):
            if hasattr(self.comment.author, 'get_full_name'):
                return self.comment.author.get_full_name() or self.comment.author.username
            return str(self.comment.author)
        
        return "Неизвестно"
    
    def get_comment_email(self):
        """Получить email автора комментария (универсальный метод)"""
        if not self.comment:
            return ""
        
        # Comment (Blog)
        if hasattr(self.comment, 'email'):
            return self.comment.email
        
        # OtzivComment
        if hasattr(self.comment, 'author_email'):
            return self.comment.author_email
        
        # OrderComment
        if hasattr(self.comment, 'author') and hasattr(self.comment.author, 'email'):
            return self.comment.author.email
        
        return ""
    
    def get_comment_content(self):
        """Получить содержимое комментария (универсальный метод)"""
        if not self.comment:
            return ""
        
        if hasattr(self.comment, 'content'):
            return self.comment.content
        
        return ""
    
    def get_related_object(self):
        """Получить связанный объект (статья, отзыв, заказ)"""
        if not self.comment:
            return None
        
        # Comment -> Post
        if hasattr(self.comment, 'post'):
            return self.comment.post
        
        # OtzivComment -> Otziv
        if hasattr(self.comment, 'otziv'):
            return self.comment.otziv
        
        # OrderComment -> Order
        if hasattr(self.comment, 'order'):
            return self.comment.order
        
        return None


class SEOAnalysis(models.Model):
    """SEO анализ статей"""
    
    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name='seo_analysis',
        verbose_name='Статья'
    )
    
    # SEO метаданные
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name='Meta Title',
        help_text='До 60 символов'
    )
    
    meta_description = models.TextField(
        max_length=160,
        blank=True,
        verbose_name='Meta Description',
        help_text='До 160 символов'
    )
    
    focus_keyword = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Фокусное ключевое слово'
    )
    
    # SEO метрики
    seo_score = models.IntegerField(
        default=0,
        verbose_name='SEO Score',
        help_text='Оценка от 0 до 100'
    )
    
    # Детальный анализ
    analysis_data = models.JSONField(
        default=dict,
        verbose_name='Данные анализа',
        help_text='Детальные результаты SEO анализа'
    )
    
    # Временные метки
    analyzed_at = models.DateTimeField(auto_now_add=True, verbose_name='Проанализировано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'SEO анализ'
        verbose_name_plural = 'SEO анализы'
        ordering = ['-analyzed_at']
        indexes = [
            models.Index(fields=['seo_score', '-analyzed_at']),
        ]
    
    def __str__(self):
        return f"SEO: {self.post.title} (Score: {self.seo_score})"


class ModerationNotification(models.Model):
    """Уведомления для модераторов"""
    
    TYPE_CHOICES = [
        ('article_pending', 'Статья ожидает модерации'),
        ('comment_pending', 'Комментарий ожидает модерации'),
        ('article_approved', 'Статья одобрена'),
        ('article_rejected', 'Статья отклонена'),
        ('seo_low_score', 'Низкий SEO score'),
    ]
    
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='moderation_notifications',
        verbose_name='Получатель'
    )
    
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='Тип уведомления'
    )
    
    title = models.CharField(max_length=512, verbose_name='Заголовок')
    message = models.TextField(verbose_name='Сообщение')
    
    # Связи с объектами
    article_moderation = models.ForeignKey(
        ArticleModeration,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Модерация статьи'
    )
    
    comment_moderation = models.ForeignKey(
        CommentModeration,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Модерация комментария'
    )
    
    seo_analysis = models.ForeignKey(
        SEOAnalysis,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='SEO анализ'
    )
    
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    
    class Meta:
        verbose_name = 'Уведомление модератора'
        verbose_name_plural = 'Уведомления модераторов'
        ordering = ['-created']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.title}"


class ModerationStatistics(models.Model):
    """Статистика модерации"""
    
    date = models.DateField(unique=True, verbose_name='Дата')
    
    # Статистика по статьям
    articles_pending = models.IntegerField(default=0, verbose_name='Статей на модерации')
    articles_approved = models.IntegerField(default=0, verbose_name='Одобрено статей')
    articles_rejected = models.IntegerField(default=0, verbose_name='Отклонено статей')
    articles_needs_revision = models.IntegerField(default=0, verbose_name='Требует доработки')
    
    # Статистика по комментариям
    comments_pending = models.IntegerField(default=0, verbose_name='Комментариев на модерации')
    comments_approved = models.IntegerField(default=0, verbose_name='Одобрено комментариев')
    comments_deleted = models.IntegerField(default=0, verbose_name='Удалено комментариев')
    comments_corrected = models.IntegerField(default=0, verbose_name='Исправлено комментариев')
    
    # SEO статистика
    seo_analyzed = models.IntegerField(default=0, verbose_name='Проанализировано статей')
    seo_avg_score = models.FloatField(default=0, verbose_name='Средний SEO score')
    seo_high_score = models.IntegerField(default=0, verbose_name='Высокий score (80+)')
    seo_low_score = models.IntegerField(default=0, verbose_name='Низкий score (<50)')
    
    # Время модерации
    avg_moderation_time = models.FloatField(default=0, verbose_name='Среднее время модерации (часы)')
    
    created = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Статистика модерации'
        verbose_name_plural = 'Статистика модерации'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date']),
        ]
    
    def __str__(self):
        return f"Статистика за {self.date}"
