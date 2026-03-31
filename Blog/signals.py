from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from .models import Post, Comment
from .utils import add_nofollow_to_external_links, add_internal_links_to_content
from home.seo_utils import SEOUtils
from Moderation.services import SEOService
import re
import logging

logger = logging.getLogger(__name__)


def _compute_meta_keywords_for_post(instance):
    """Теги + ключевые слова из контента и заголовка (до 10 фраз)."""
    keywords_list = []
    if instance.pk:
        try:
            keywords_list.extend(instance.tags.values_list('name', flat=True))
        except Exception:
            pass
    if instance.content:
        keywords_list.extend(SEOUtils.extract_keywords(instance.content, max_keywords=5))
    if instance.title:
        keywords_list.extend(SEOUtils.extract_keywords(instance.title, max_keywords=3))
    unique_keywords = list(dict.fromkeys(keywords_list))[:10]
    return ', '.join(unique_keywords)


def safe_log_text(text: str) -> str:
    """
    Безопасное преобразование текста для логирования в Windows cp1251
    Убирает эмодзи и небезопасные Unicode символы
    """
    if not text:
        return ''
    try:
        # Простой способ: убираем все символы, которые нельзя закодировать в cp1251
        # Сохраняем кириллицу и ASCII
        safe_text = text.encode('cp1251', errors='ignore').decode('cp1251', errors='ignore')
        return safe_text
    except Exception:
        # Если не получилось - возвращаем только ASCII
        try:
            return text.encode('ascii', 'ignore').decode('ascii')
        except Exception:
            return str(text)[:100]  # Ограничиваем длину на случай проблем


@receiver(pre_save, sender=Post)
def generate_seo_meta_tags(sender, instance, **kwargs):
    """Автогенерация SEO мета-тегов перед сохранением статьи"""
    try:
        # Генерация slug если не указан
        if not instance.slug and instance.title:
            # Генерируем slug из заголовка
            base_slug = slugify(instance.title)
            
            # Если slug пустой (например, только спецсимволы), используем дефолтный
            if not base_slug:
                base_slug = 'post'
            
            # Проверяем уникальность (с учетом unique_for_date)
            original_slug = base_slug
            counter = 1
            
            # Если статья уже существует (pk есть), используем её created для проверки unique_for_date
            # Если это новая статья, используем текущую дату
            if instance.pk:
                # Для существующей статьи используем её дату создания
                created_date = instance.created.date() if instance.created else timezone.now().date()
                queryset = Post.objects.filter(
                    slug=base_slug,
                    created__date=created_date
                ).exclude(pk=instance.pk)
            else:
                # Для новой статьи проверяем по текущей дате
                created_date = timezone.now().date()
                queryset = Post.objects.filter(
                    slug=base_slug,
                    created__date=created_date
                )
            
            # Если нашли дубликаты, добавляем номер
            while queryset.exists():
                base_slug = f"{original_slug}-{counter}"
                if instance.pk:
                    queryset = Post.objects.filter(
                        slug=base_slug,
                        created__date=created_date
                    ).exclude(pk=instance.pk)
                else:
                    queryset = Post.objects.filter(
                        slug=base_slug,
                        created__date=created_date
                    )
                counter += 1
                # Защита от бесконечного цикла
                if counter > 1000:
                    base_slug = f"{original_slug}-{instance.pk or timezone.now().timestamp()}"
                    break
            
            instance.slug = base_slug
            logger.debug(f"[SEO] Сгенерирован slug для статьи: {instance.slug}")
        
        # Генерация meta_title если не указан
        if not instance.meta_title and instance.title:
            instance.meta_title = SEOUtils.generate_meta_title(instance.title)
        
        # Meta description: из описания/контента или нормализация уже введённого (markdown, длина ≤160)
        if not (instance.meta_description or '').strip():
            if instance.description:
                instance.meta_description = SEOUtils.generate_meta_description(instance.description)
            elif instance.content:
                raw = re.sub(r'<[^>]+>', ' ', instance.content or '')
                snippet = ' '.join(SEOUtils.plain_text_for_meta(raw).split()[:25])
                instance.meta_description = SEOUtils.generate_meta_description(snippet)
        if (instance.meta_description or '').strip():
            instance.meta_description = SEOUtils.generate_meta_description(instance.meta_description, 160)

        # Meta keywords: автоматически, если поле пустое (теги подтянутся после save через m2m_changed)
        if not (instance.meta_keywords or '').strip():
            instance.meta_keywords = _compute_meta_keywords_for_post(instance)
        
        # Генерация focus_keyword если не указан
        if not instance.focus_keyword and instance.title:
            # Берем первое значимое слово из заголовка
            words = instance.title.split()
            # Фильтруем стоп-слова
            stop_words = {'как', 'что', 'для', 'при', 'без', 'под', 'над', 'из', 'от', 'до', 'по', 'со', 'во'}
            focus_words = [w.lower() for w in words if w.lower() not in stop_words and len(w) > 3]
            if focus_words:
                instance.focus_keyword = focus_words[0]
            else:
                instance.focus_keyword = words[0] if words else ''
        
        # Автоматическое добавление rel="nofollow" к внешним ссылкам в контенте
        if instance.content:
            instance.content = add_nofollow_to_external_links(instance.content)
        
        # Автоматическая внутренняя перелинковка (только для опубликованных статей)
        # Добавляем ссылки только если их еще нет в контенте
        if instance.status == 'published' and instance.content and instance.pk:
            # Проверяем, есть ли уже внутренние ссылки в контенте
            # Если ссылок мало (менее 3), добавляем автоматически
            internal_links_count = len(re.findall(r'<a[^>]+href=["\']/[^"\']+["\']', instance.content))
            if internal_links_count < 3:
                # Добавляем внутренние ссылки (максимум 3-5)
                instance.content = add_internal_links_to_content(instance, instance.content, max_links=3)
        
        # Безопасное логирование заголовка (убираем эмодзи для Windows cp1251)
        safe_title = safe_log_text(instance.title) if instance.title else ''
        logger.info(f"[SEO] Автогенерация SEO мета-тегов для статьи: {safe_title}")
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при автогенерации SEO мета-тегов: {str(e)}", exc_info=True)


@receiver(m2m_changed, sender=Post.tags.through)
def post_tags_changed_fill_meta_keywords(sender, instance, action, **kwargs):
    """
    После привязки тегов в админке keywords в pre_save ещё без тегов — дозаполняем, если поле пустое.
    """
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    if not isinstance(instance, Post) or not instance.pk:
        return
    try:
        fresh = Post.objects.get(pk=instance.pk)
    except Post.DoesNotExist:
        return
    if (fresh.meta_keywords or '').strip():
        return
    kw = _compute_meta_keywords_for_post(fresh)
    if kw:
        Post.objects.filter(pk=fresh.pk).update(meta_keywords=kw)


@receiver(post_save, sender=Post)
def analyze_post_seo(sender, instance, created, **kwargs):
    """Автоматический SEO анализ после сохранения статьи"""
    try:
        # Анализируем только опубликованные статьи
        if instance.status == 'published':
            seo_service = SEOService()
            analysis_result = seo_service.analyze_post(instance)
            
            # Сохраняем SEO score в поле статьи
            instance.seo_score = analysis_result['score']
            # Обновляем без триггера сигналов
            Post.objects.filter(pk=instance.pk).update(seo_score=analysis_result['score'])
            
            safe_title = safe_log_text(instance.title) if instance.title else ''
            logger.info(f"[SEO] SEO анализ завершен для статьи {safe_title}: score={analysis_result['score']}")
            
            # Если score низкий, можно добавить уведомление автору
            if analysis_result['score'] < 50:
                logger.warning(f"[SEO] Низкий SEO score ({analysis_result['score']}) для статьи: {safe_title}")
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при SEO анализе статьи: {str(e)}", exc_info=True)


@receiver(post_save, sender=Post)
def submit_to_search_engines(sender, instance, created, **kwargs):
    """Отправка в поисковые системы при публикации статьи"""
    try:
        # Отправляем только опубликованные статьи
        if instance.status == 'published':
            should_submit = False
            
            if created:
                # Новая статья сразу опубликована
                should_submit = True
            else:
                # Для существующих статей проверяем, изменился ли статус на published
                # Используем update_fields из kwargs, если он есть
                update_fields = kwargs.get('update_fields')
                
                if update_fields is None:
                    # Если update_fields не указан, значит обновлялись все поля
                    # Проверяем через БД - получаем старую версию до сохранения
                    # Но в post_save уже сохранено, поэтому используем другой подход
                    # Отправляем только если это не массовое обновление
                    should_submit = True
                elif 'status' in update_fields:
                    # Статус был явно обновлен - проверяем, что он стал published
                    # В post_save уже сохранено, поэтому просто отправляем
                    should_submit = True
                # Если update_fields указан, но status не входит - значит статус не менялся
                # и статья уже была опубликована, не отправляем повторно
            
            if should_submit:
                try:
                    from Assistant.search_engines_submitter import SearchEnginesSubmitter
                    submitter = SearchEnginesSubmitter()
                    results = submitter.submit_all(instance)
                    
                    success_count = sum(1 for r in results.values() if r.get('success', False))
                    safe_title = safe_log_text(instance.title) if instance.title else ''
                    logger.info(f"[SUBMIT] Статья отправлена в поисковые системы: {safe_title} ({success_count}/3 успешно)")
                except ImportError:
                    logger.warning("[SUBMIT] Модуль SearchEnginesSubmitter не найден, пропускаем отправку")
                except Exception as e:
                    logger.error(f"[SUBMIT] Ошибка отправки в поисковые системы: {str(e)}", exc_info=True)
        
    except Exception as e:
        logger.error(f"[SUBMIT] Ошибка при отправке в поисковые системы: {str(e)}", exc_info=True)


@receiver(pre_save, sender=Comment)
def add_nofollow_to_comment_links(sender, instance, **kwargs):
    """Автоматическое добавление rel="nofollow" к внешним ссылкам в комментариях"""
    try:
        if instance.content:
            # Обрабатываем только текстовые ссылки (не HTML)
            # Если в комментарии есть HTML теги <a>, обрабатываем их
            if '<a' in instance.content.lower() or 'href=' in instance.content.lower():
                instance.content = add_nofollow_to_external_links(instance.content)
            else:
                # Если это простой текст со ссылками, можно добавить обработку URL
                # Но обычно комментарии не содержат HTML, так что пропускаем
                pass
        
        logger.debug(f"[SEO] Обработка ссылок в комментарии от {instance.author_comment}")
        
    except Exception as e:
        logger.error(f"[SEO] Ошибка при обработке ссылок в комментарии: {str(e)}", exc_info=True)

