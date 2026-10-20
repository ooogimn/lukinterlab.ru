"""
Задачи для автоматизации SEO и других процессов
"""
import logging
from django.core.management import call_command
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from home.models import SEOModel
from Assistant.models import AssistantKnowledge

logger = logging.getLogger(__name__)


def optimize_seo_task():
    """Автоматическая SEO оптимизация для AI/ИИ запросов"""
    try:
        logger.info("[SEO] Запуск автоматической SEO оптимизации...")
        call_command('optimize_seo_for_ai', verbosity=0)
        logger.info("[SEO] SEO оптимизация завершена успешно")
        return True
    except Exception as e:
        logger.error(f"[SEO] Ошибка при SEO оптимизации: {str(e)}", exc_info=True)
        return False


def update_knowledge_base_task():
    """Обновление базы знаний для AI-ассистента"""
    try:
        logger.info("[AI] Запуск обновления базы знаний...")
        call_command('create_ai_knowledge_base', verbosity=0)
        logger.info("[AI] База знаний обновлена успешно")
        return True
    except Exception as e:
        logger.error(f"[AI] Ошибка при обновлении базы знаний: {str(e)}", exc_info=True)
        return False


def ping_search_engines():
    """Отправка уведомлений поисковым системам об обновлении sitemap"""
    try:
        from django.conf import settings
        import requests
        
        sitemap_url = f"{getattr(settings, 'SITE_URL', 'https://lukinterlab.ru')}/sitemap.xml"
        
        # Google
        try:
            google_ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
            response = requests.get(google_ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("[SEO] Google уведомлен об обновлении sitemap")
        except Exception as e:
            logger.warning(f"[SEO] Ошибка уведомления Google: {str(e)}")
        
        # Yandex
        try:
            yandex_ping_url = f"https://webmaster.yandex.ru/ping?sitemap={sitemap_url}"
            response = requests.get(yandex_ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("[SEO] Yandex уведомлен об обновлении sitemap")
        except Exception as e:
            logger.warning(f"[SEO] Ошибка уведомления Yandex: {str(e)}")
        
        # Bing
        try:
            bing_ping_url = f"https://www.bing.com/ping?sitemap={sitemap_url}"
            response = requests.get(bing_ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("[SEO] Bing уведомлен об обновлении sitemap")
        except Exception as e:
            logger.warning(f"[SEO] Ошибка уведомления Bing: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"[SEO] Ошибка при отправке уведомлений поисковикам: {str(e)}", exc_info=True)
        return False


def send_contact_notifications(contact_message_id):
    """Новая заявка с формы «Контакты»: письмо (с вложением, «Ответить» — посетителю), Telegram, MAX."""
    from home.models import ContactMessage
    from home.notify import notify_admin

    msg = ContactMessage.objects.filter(pk=contact_message_id).first()
    if msg is None or msg.is_spam:
        return None

    site_url = settings.SITE_URL
    created = timezone.localtime(msg.created).strftime('%d.%m.%Y %H:%M')
    attachment_name = msg.get_attachment_filename() if msg.attachment else ''
    admin_url = f"{site_url}/admin/home/contactmessage/{msg.pk}/change/"
    header = (
        f"Имя: {msg.name}\n"
        f"Email: {msg.email}\n"
        f"Дата: {created}\n"
    )
    text = (
        header
        + f"IP: {msg.ip_address or '—'}\n\n"
        + f"{msg.message}\n\n"
        + (f"Вложение: {attachment_name} (приложено к письму)\n" if attachment_name else "")
        + f"В админке: {admin_url}\n"
    )
    short_message = msg.message if len(msg.message) <= 700 else msg.message[:700] + "…"
    short_text = (
        header
        + f"\n{short_message}\n\n"
        + (f"Вложение: {attachment_name} — в письме и в админке\n" if attachment_name else "")
        + f"{admin_url}"
    )

    attachments = []
    if msg.attachment:
        try:
            attachments.append((msg.attachment.path, msg.attachment.size))
        except Exception:
            logger.warning("Уведомление: вложение заявки %s не найдено на диске", msg.pk)

    return notify_admin(
        f"Новая заявка с сайта: {msg.name}",
        text,
        short_text=short_text,
        attachments=attachments,
        reply_to=msg.email,
    )


ORDER_NOTIFICATION_TITLES = {
    'created': 'Новый заказ',
    'questionnaire': 'Заполнена анкета заказа',
    'paid': 'Заказ оплачен',
}


def send_order_notifications(order_id, event='created'):
    """Заказ: оформлен (created), заполнена анкета (questionnaire), оплачен (paid) — письмо, Telegram, MAX."""
    from home.models import Order
    from home.notify import notify_admin

    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return None
    title = ORDER_NOTIFICATION_TITLES.get(event, 'Заказ')

    lines = [
        f"Заказ №{order.order_number} от {timezone.localtime(order.created).strftime('%d.%m.%Y %H:%M')}",
        f"Клиент: {order.customer_name}",
        f"Email: {order.customer_email}",
        f"Телефон: {order.customer_phone}",
        f"Сумма заказа: {order.total_price} ₽",
    ]
    if event == 'paid':
        lines.append(f"Оплачено (предоплата): {order.get_prepayment_amount()} ₽")
    elif order.prepayment_amount:
        lines.append(f"Предоплата к оплате: {order.prepayment_amount} ₽")

    items = [f"• {item.title} × {item.quantity} — {item.price}" for item in order.orderitem_set.all()]
    if items:
        lines += ["", "Состав:"] + items

    if event == 'questionnaire':
        questionnaire = getattr(order, 'questionnaire', None)
        if questionnaire is not None and questionnaire.project_name:
            lines += ["", f"Проект: {questionnaire.project_name}"]
        files_count = order.files.count()
        if files_count:
            lines.append(f"Файлов приложено: {files_count}")

    lines += ["", f"В панели: {settings.SITE_URL}/manage/order/{order.id}/"]
    return notify_admin(f"{title}: №{order.order_number}", "\n".join(lines))


def cleanup_old_sessions():
    """Очистка старых сессий корзины"""
    try:
        from home.models import Cart
        from django.utils import timezone
        from datetime import timedelta
        
        # Удаляем корзины старше 30 дней
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted_count = Cart.objects.filter(updated__lt=cutoff_date).delete()[0]
        
        logger.info(f"[CLEANUP] Удалено {deleted_count} старых корзин")
        return deleted_count
    except Exception as e:
        logger.error(f"[CLEANUP] Ошибка при очистке корзин: {str(e)}", exc_info=True)
        return 0
