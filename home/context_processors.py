from .models import SEOModel, SectionBackground, LegalInfo, SiteMarketingSettings
from django.conf import settings
from django.core.cache import cache

def seo_meta_tags(request):
    """Контекст-процессор для SEO мета-тегов с кэшированием"""
    current_path = request.path
    cache_key = f'seo_meta_{current_path}'
    
    # Пытаемся получить из кэша
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    
    try:
        seo_data = SEOModel.objects.only(
            'title', 'description', 'keywords', 'og_title', 'og_description', 
            'og_image', 'canonical_url', 'h1'
        ).get(page_url=current_path)
        
        result = {
            'seo_title': seo_data.title,
            'seo_description': seo_data.description,
            'seo_keywords': seo_data.keywords,
            'seo_og_title': seo_data.get_og_title(),
            'seo_og_description': seo_data.get_og_description(),
            'seo_og_image': seo_data.og_image,
            'seo_canonical_url': seo_data.canonical_url,
            'seo_h1': seo_data.h1,
        }
    except SEOModel.DoesNotExist:
        result = {
            'seo_title': 'LukInterLab - AI и IT решения под ключ',
            'seo_description': 'Создаем сайты, боты, приложения и интернет-магазины с искусственным интеллектом. Специализируемся на LLM, интеграции GigaChat, GPT, Gemini, DeepSeek, Grok. Саморекламирующие сайты, самопродающие магазины.',
            'seo_keywords': 'искусственный интеллект, ИИ, AI, LLM, GigaChat, GPT, Gemini, DeepSeek, Grok, саморекламирующие сайты, самопродающие магазины, ИИ-маркетинг, интеграция ИИ в бизнес, разработка сайтов, телеграм боты, мобильные приложения, интернет магазин, IT услуги',
            'seo_og_title': 'LukInterLab - AI и IT решения под ключ',
            'seo_og_description': 'Создаем сайты, боты, приложения и интернет-магазины с искусственным интеллектом. Специализируемся на LLM, интеграции GigaChat, GPT, Gemini, DeepSeek, Grok.',
            'seo_og_image': None,
            'seo_canonical_url': None,
            'seo_h1': 'LukInterLab - AI и IT решения под ключ',
        }
    
    # Кэшируем на 1 час (3600 секунд)
    cache.set(cache_key, result, 3600)
    return result


def section_backgrounds(request):
    """Контекст-процессор для фонов секций с кэшированием"""
    cache_key = 'section_backgrounds_all'
    
    # Пытаемся получить из кэша
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    
    try:
        backgrounds = {}
        section_backgrounds = SectionBackground.objects.filter(
            is_active=True
        ).only(
            'section', 'background_type', 'background_image', 'background_video',
            'gradient_start', 'gradient_end', 'gradient_direction',
            'overlay_opacity', 'overlay_color'
        )
        
        for bg in section_backgrounds:
            backgrounds[bg.section] = {
                'type': bg.background_type,
                'background_style': bg.get_background_style(),
                'overlay_style': bg.get_overlay_style(),
                'video_url': bg.get_video_url(),
                'has_overlay': bg.overlay_opacity > 0,
            }
        
        result = {'section_backgrounds': backgrounds}
    except Exception:
        result = {'section_backgrounds': {}}
    
    # Кэшируем на 1 час (3600 секунд)
    cache.set(cache_key, result, 3600)
    return result


def cart_info(request):
    """Контекст-процессор для информации о корзине"""
    cart_items_count = 0
    
    if request.session.session_key:
        try:
            from .models import Cart
            # Используем select_related для оптимизации
            cart = Cart.objects.select_related().filter(
                session_key=request.session.session_key
            ).first()
            if cart:
                # Используем count() вместо get_items_count() для оптимизации
                cart_items_count = cart.items.count()
        except:
            pass
    
    return {
        'cart_items_count': cart_items_count
    }


def legal_info_context(request):
    """Контекст-процессор для правовой информации с кэшированием"""
    cache_key = 'legal_info_context_active'
    
    # Пытаемся получить из кэша
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    
    try:
        legal_info_obj = LegalInfo.objects.filter(is_active=True).only(
            'id', 'phone', 'email', 'company_name', 'is_active'
        ).first()
        if not legal_info_obj:
            legal_info_obj = LegalInfo()
        
        # Обрабатываем телефон для tel: ссылки (убираем пробелы, скобки, дефисы)
        phone_for_link = legal_info_obj.phone or '+7-905-856-02-82'
        phone_for_link = phone_for_link.replace(' ', '').replace('(', '').replace(')', '').replace('-', '')
        
        result = {
            'legal_info': legal_info_obj,
            'phone_for_link': phone_for_link,
        }
    except Exception:
        result = {
            'legal_info': None,
            'phone_for_link': '79058560282',
        }
    
    # Кэшируем на 1 час (3600 секунд)
    cache.set(cache_key, result, 3600)
    return result


def site_marketing_context(request):
    """Реклама, РСЯ, заменяемые счётчики — из БД (редакция /manage/marketing/)."""
    cache_key = 'site_marketing_ctx'
    data = cache.get(cache_key)
    if data is None:
        s = SiteMarketingSettings.get_solo()
        data = {
            'active': s.active,
            'replace_builtin_counters': s.replace_builtin_counters,
            'yandex_metrika_html': s.yandex_metrika_html or '',
            'google_tag_head_html': s.google_tag_head_html or '',
            'google_tag_body_html': s.google_tag_body_html or '',
            'head_extra_html': s.head_extra_html or '',
            'body_end_html': s.body_end_html or '',
            'yandex_rsya_html': s.yandex_rsya_html or '',
            'custom_promo_banner_html': s.custom_promo_banner_html or '',
            'promo_image_url': s.promo_image.url if s.promo_image else '',
            'promo_link': s.promo_link or '',
        }
        cache.set(cache_key, data, 1800)
    return {'site_marketing': data}


def header_customer_avatar(request):
    """URL аватара заказчика для шапки (публичный сайт)."""
    from django.templatetags.static import static

    if not request.user.is_authenticated:
        return {'header_customer_avatar_url': None}
    try:
        from .models import Customer

        c = Customer.objects.filter(user=request.user).only('avatar').first()
        if c and c.avatar:
            return {'header_customer_avatar_url': c.avatar.url}
    except Exception:
        pass
    return {'header_customer_avatar_url': static('img/favicon.svg')}