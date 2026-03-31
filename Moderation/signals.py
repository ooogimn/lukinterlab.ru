from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from Blog.models import Post, Comment
from .models import ArticleModeration, CommentModeration
from .services import NotificationService, CommentModerationService
import logging

logger = logging.getLogger(__name__)

notification_service = NotificationService()
comment_moderation_service = CommentModerationService()


@receiver(post_save, sender=Post)
def create_article_moderation(sender, instance, created, **kwargs):
    """Создание записи модерации при создании статьи"""
    if created and instance.status == 'draft':
        moderation, created_mod = ArticleModeration.objects.get_or_create(
            post=instance,
            defaults={'status': 'pending'}
        )
        if created_mod:
            notification_service.notify_article_pending(moderation)
    elif not created and instance.status == 'draft':
        # Если статья переведена в черновик, создаем модерацию если её нет
        moderation, created_mod = ArticleModeration.objects.get_or_create(
            post=instance,
            defaults={'status': 'pending'}
        )
        if created_mod:
            notification_service.notify_article_pending(moderation)


@receiver(post_save, sender=Post)
def sync_article_moderation_when_published(sender, instance, **kwargs):
    """
    Публикация статьи (Post.status=published) раньше не обновляла ArticleModeration —
    в дашборде оставались «ожидают модерации» при уже живых на сайте постах.
    """
    if instance.status != 'published' or not instance.pk:
        return
    ArticleModeration.objects.filter(
        post_id=instance.pk,
        status__in=('pending', 'needs_revision'),
    ).update(status='approved', moderated_at=timezone.now())


def _auto_moderate_comment_handler(sender, instance, created, **kwargs):
    """
    Универсальный обработчик автоматической модерации комментариев (для всех типов)
    
    Процесс:
    1. При сохранении нового комментария автоматически запускается проверка
    2. Проверка идет по активным критериям модерации
    3. В зависимости от результатов и настроек критерия (delete / correct / reply) применяется действие:
       approved, deleted, hidden, corrected, replied — как задано в админке для активного критерия
    """
    # Пропускаем, если это обновление существующего комментария (не создание)
    if not created:
        return
    
    try:
        # Универсальная проверка на ответ администратора
        is_admin = False
        if hasattr(instance, 'is_admin_reply'):
            is_admin = instance.is_admin_reply
        elif hasattr(instance, 'is_admin_comment'):
            is_admin = instance.is_admin_comment
        
        comment_type_str = f"{sender._meta.app_label}.{sender._meta.model_name}"
        logger.info(f"[AUTO_MODERATE] Сигнал сработал для комментария {instance.id} (Type: {comment_type_str}). Created: {created}, Is admin: {is_admin}")
        
        # Пропускаем модерацию для ответов администратора
        if is_admin:
            logger.info(f"[AUTO_MODERATE] Пропуск модерации для ответа администратора (комментарий {instance.id})")
            return
        
        # Получаем содержимое комментария
        content = getattr(instance, 'content', '') or ''
        
        # Запускаем автоматическую модерацию
        logger.info(f"[AUTO_MODERATE] Запуск автоматической модерации для комментария {instance.id}. Content: {content[:50] if content else 'EMPTY'}...")
        try:
            result = comment_moderation_service.moderate_comment(instance)
            logger.info(f"[AUTO_MODERATE] Модерация завершена для комментария {instance.id}. Result keys: {list(result.keys())}")
        except Exception as e:
            logger.error(f"[AUTO_MODERATE] КРИТИЧЕСКАЯ ОШИБКА при вызове moderate_comment для комментария {instance.id}: {str(e)}", exc_info=True)
            raise
        
        if result.get('error'):
            logger.warning(f"[AUTO_MODERATE] Ошибка модерации комментария {instance.id}: {result.get('error')}")
            try:
                content_type = ContentType.objects.get_for_model(instance)
                comment_type_str = f"{content_type.app_label}.{content_type.model}"
                CommentModeration.objects.get_or_create(
                    content_type=content_type,
                    object_id=instance.id,
                    defaults={'comment_type': comment_type_str},
                )
                moderation = CommentModeration.objects.get(content_type=content_type, object_id=instance.id)
                notification_service.notify_comment_pending(moderation)
                logger.info(f"[AUTO_MODERATE] Создана запись модерации для ручной проверки комментария {instance.id}")
                if hasattr(instance, 'active'):
                    sender.objects.filter(pk=instance.pk).update(active=False)
                    logger.info(f"[AUTO_MODERATE] Комментарий {instance.id} скрыт из-за ошибки модерации (active=False)")
            except Exception as e:
                logger.error(
                    f"[AUTO_MODERATE] Ошибка при создании записи модерации для комментария {instance.id}: {str(e)}",
                    exc_info=True,
                )
        else:
            action = result.get('action', 'approved')
            deleted = result.get('deleted', False)

            logger.info(f"[AUTO_MODERATE] Результат модерации комментария {instance.id}: action={action}, deleted={deleted}")

            if deleted:
                logger.info(f"[AUTO_MODERATE] Комментарий {instance.id} был удален после модерации. Прекращаем обработку.")
                return

            logger.info(f"[AUTO_MODERATE] Комментарий {instance.id} промодерирован: действие = {action}")

            if action in ['hidden', 'deleted', 'corrected', 'replied']:
                moderation = result.get('moderation')
                if moderation:
                    try:
                        notification_service.notify_comment_pending(moderation)
                        logger.info(f"[AUTO_MODERATE] Уведомление отправлено для комментария {instance.id}")
                    except Exception as e:
                        logger.error(
                            f"[AUTO_MODERATE] Ошибка при отправке уведомления для комментария {instance.id}: {str(e)}",
                            exc_info=True,
                        )

    except Exception as e:
        logger.error(
            f"[AUTO_MODERATE] КРИТИЧЕСКАЯ ОШИБКА при автоматической модерации комментария {instance.id}: {str(e)}",
            exc_info=True,
        )
        try:
            content_type = ContentType.objects.get_for_model(instance)
            comment_type_str = f"{content_type.app_label}.{content_type.model}"
            CommentModeration.objects.get_or_create(
                content_type=content_type,
                object_id=instance.id,
                defaults={'comment_type': comment_type_str},
            )
            logger.info(f"[AUTO_MODERATE] Создана запись модерации для ручной проверки после ошибки (комментарий {instance.id})")
            if hasattr(instance, 'active'):
                sender.objects.filter(pk=instance.pk).update(active=False)
        except Exception as e2:
            logger.error(
                f"[AUTO_MODERATE] Не удалось создать запись модерации после ошибки для комментария {instance.id}: {str(e2)}",
                exc_info=True,
            )


# Подключаем сигналы для всех типов комментариев
@receiver(post_save, sender=Comment)
def auto_moderate_comment(sender, instance, created, **kwargs):
    """Автоматическая модерация комментариев к статьям"""
    _auto_moderate_comment_handler(sender, instance, created, **kwargs)


# Импортируем модели для явного указания sender
def register_comment_signals():
    """Регистрация сигналов для всех типов комментариев"""
    try:
        from home.models import OtzivComment, OrderComment
        
        # Регистрируем сигнал для OtzivComment через connect (более надежный способ)
        def otziv_comment_handler(sender, instance, created, **kwargs):
            """Автоматическая модерация комментариев к отзывам"""
            logger.info(f"[OTZIV_SIGNAL] Сигнал сработал! Comment ID: {instance.id}, Created: {created}, Content: {instance.content[:50] if hasattr(instance, 'content') else 'NO CONTENT'}...")
            _auto_moderate_comment_handler(sender, instance, created, **kwargs)
        
        def order_comment_handler(sender, instance, created, **kwargs):
            """Автоматическая модерация комментариев к заказам"""
            logger.info(f"[ORDER_SIGNAL] Сигнал сработал! Comment ID: {instance.id}, Created: {created}")
            _auto_moderate_comment_handler(sender, instance, created, **kwargs)
        
        # Подключаем сигналы через connect с weak=False для надежности
        post_save.connect(otziv_comment_handler, sender=OtzivComment, weak=False, dispatch_uid='moderation_otziv_comment')
        post_save.connect(order_comment_handler, sender=OrderComment, weak=False, dispatch_uid='moderation_order_comment')
            
        logger.info(f"[SIGNALS] Сигналы для OtzivComment и OrderComment успешно зарегистрированы через connect() (dispatch_uid установлен)")
    except ImportError as e:
        logger.warning(f"[SIGNALS] Не удалось импортировать модели комментариев: {str(e)}")
    except Exception as e:
        logger.error(f"[SIGNALS] Ошибка при регистрации сигналов: {str(e)}", exc_info=True)


# Вызываем регистрацию сигналов
register_comment_signals()


@receiver(post_save, sender=ArticleModeration)
def update_article_moderation_time(sender, instance, **kwargs):
    """Обновление времени модерации при изменении статуса"""
    if instance.status != 'pending' and instance.moderated_at is None:
        instance.moderated_at = timezone.now()
        instance.save(update_fields=['moderated_at'])


@receiver(post_save, sender=CommentModeration)
def update_comment_moderation_time(sender, instance, **kwargs):
    """Обновление времени модерации при установке действия"""
    if instance.action and instance.moderated_at is None:
        instance.moderated_at = timezone.now()
        instance.save(update_fields=['moderated_at'])

