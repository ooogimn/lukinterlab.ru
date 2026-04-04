from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import (
    Otziv,
    Rabota,
    RabotaMedia,
    Service,
    StandaloneExtraService,
    LegalInfo,
    SiteMarketingSettings,
    SectionBackground,
)
from Blog.models import Post


@receiver([post_save, post_delete], sender=Post)
def clear_home_cache_on_post_change(sender, instance, **kwargs):
    """Очистка кэша главной страницы при изменении постов блога"""
    if kwargs.get('raw'):
        return
    cache.delete('home_page_data')
    cache.delete('legal_info_active')


@receiver([post_save, post_delete], sender=Otziv)
def clear_home_cache_on_otziv_change(sender, instance, **kwargs):
    """Очистка кэша главной страницы при изменении отзывов"""
    if kwargs.get('raw'):
        return
    cache.delete('home_page_data')


@receiver([post_save, post_delete], sender=RabotaMedia)
def clear_home_cache_on_rabota_media_change(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    cache.delete('home_rabotas')
    cache.delete('home_page_data')


@receiver([post_save, post_delete], sender=Rabota)
def clear_home_cache_on_rabota_change(sender, instance, **kwargs):
    """Очистка кэша главной страницы при изменении работ"""
    if kwargs.get('raw'):
        return
    cache.delete('home_page_data')
    cache.delete('home_rabotas')  # Очищаем кэш работ
    
    # Удаляем старые WebP версии при изменении изображения
    if instance.pk and hasattr(instance, 'image') and instance.image:
        try:
            # Удаляем WebP версии для перегенерации
            if hasattr(instance, 'thumbnail_webp') and instance.thumbnail_webp:
                try:
                    instance.thumbnail_webp.delete(save=False)
                except Exception:
                    pass
            
            if hasattr(instance, 'image_webp') and instance.image_webp:
                try:
                    instance.image_webp.delete(save=False)
                except Exception:
                    pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибка удаления WebP версий: {str(e)}")


@receiver([post_save, post_delete], sender=Service)
def clear_home_cache_on_service_change(sender, instance, **kwargs):
    """Очистка кэша главной страницы при изменении услуг"""
    if kwargs.get('raw'):
        return
    cache.delete('home_page_data')


@receiver([post_save, post_delete], sender=StandaloneExtraService)
def clear_home_cache_on_extra_service_change(sender, instance, **kwargs):
    """Очистка кэша главной страницы при изменении дополнительных услуг"""
    if kwargs.get('raw'):
        return
    cache.delete('home_page_data')


@receiver([post_save, post_delete], sender=LegalInfo)
def clear_legal_info_cache(sender, instance, **kwargs):
    """Очистка кэша правовой информации при её изменении"""
    if kwargs.get('raw'):
        return
    cache.delete('legal_info_active')
    cache.delete('home_page_data')


@receiver([post_save], sender=SiteMarketingSettings)
def clear_site_marketing_cache(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    cache.delete('site_marketing_ctx')


@receiver([post_save, post_delete], sender=SectionBackground)
def clear_section_backgrounds_cache(sender, instance, **kwargs):
    """Фоны секций в шаблонах берутся из кэша section_backgrounds_all (context_processors)."""
    if kwargs.get('raw'):
        return
    cache.delete('section_backgrounds_all')

