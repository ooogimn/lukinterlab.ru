import os
import requests
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from telegram import Bot
import asyncio
import threading
from django.db import transaction
from django.core.cache import cache
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    @staticmethod
    def send_all_notifications(contact_message):
        """Отправка всех уведомлений через django-Q"""
        try:
            from django_q.tasks import async_task
            async_task('home.tasks.send_contact_notifications', contact_message.id)
            logger.info(f"Запланирована отправка уведомлений для сообщения {contact_message.id}")
        except Exception as e:
            logger.error(f"Ошибка планирования уведомлений: {e}")
    
    @staticmethod
    def send_email_notification(contact_message):
        """Отправка email уведомления администратору"""
        try:
            subject = f'Новое сообщение с сайта от {contact_message.name}'
            
            # HTML шаблон для email
            html_content = render_to_string('home/email/contact_notification.html', {
                'message': contact_message,
                'site_url': settings.SITE_URL
            })
            
            # Текстовый шаблон для email
            text_content = f"""
Новое сообщение с сайта LukInterLab

От: {contact_message.name} ({contact_message.email})
Дата: {contact_message.created.strftime('%d.%m.%Y %H:%M')}
IP: {contact_message.ip_address or 'Неизвестно'}

Сообщение:
{contact_message.message}

---
Это автоматическое уведомление с сайта {settings.SITE_URL}
            """
            
            # Отправляем email
            email = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.ADMIN_EMAIL],
                reply_to=[contact_message.email]
            )
            email.content_subtype = "html"
            
            # Добавляем вложение, если есть
            if contact_message.attachment:
                email.attach_file(contact_message.attachment.path)
            
            email.send()
            return True
            
        except Exception as e:
            print(f"Ошибка отправки email: {e}")
            return False
    
    @staticmethod
    def send_auto_reply(contact_message):
        """Отправка автоматического ответа пользователю"""
        try:
            subject = 'Спасибо за ваше сообщение - LukInterLab'
            
            html_content = render_to_string('home/email/auto_reply.html', {
                'name': contact_message.name,
                'site_url': settings.SITE_URL
            })
            
            text_content = f"""
Здравствуйте, {contact_message.name}!

Спасибо за ваше сообщение. Мы получили его и свяжемся с вами в ближайшее время.

Ваше сообщение:
{contact_message.message}

С уважением,
Команда LukInterLab
{settings.SITE_URL}
            """
            
            send_mail(
                subject=subject,
                message=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[contact_message.email],
                html_message=html_content
            )
            return True
            
        except Exception as e:
            print(f"Ошибка отправки автоответа: {e}")
            return False
    
    @staticmethod
    def send_telegram_notification(contact_message):
        """Отправка уведомления в Telegram"""
        try:
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            
            message_text = f"""
🔔 *Новое сообщение с сайта*

👤 *От:* {contact_message.name}
📧 *Email:* {contact_message.email}
📅 *Дата:* {contact_message.created.strftime('%d.%m.%Y %H:%M')}
🌐 *IP:* {contact_message.ip_address or 'Неизвестно'}

💬 *Сообщение:*
{contact_message.message[:500]}{'...' if len(contact_message.message) > 500 else ''}

🔗 [Открыть в админке]({settings.SITE_URL}/admin/home/contactmessage/{contact_message.id}/change/)
            """
            
            # Отправляем в Telegram канал
            bot.send_message(
                chat_id=settings.TELEGRAM_CHANNEL_ID,
                text=message_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return True
            
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")
            return False


class SpamProtectionService:
    """Сервис для защиты от спама"""
    
    @staticmethod
    def track_request(ip_address, action='contact'):
        """Трекинг запросов для аналитики"""
        try:
            cache_key = f'request_track_{action}_{ip_address}'
            count = cache.get(cache_key, 0)
            cache.set(cache_key, count + 1, 3600)
            
            # Фоновый анализ подозрительных IP
            if count > 10:
                from django_q.tasks import async_task
                async_task('home.tasks.analyze_suspicious_ip', ip_address)
                
        except Exception as e:
            logger.error(f"Ошибка трекинга запроса: {e}")
    
    @staticmethod
    def check_spam(contact_message):
        """Продвинутая проверка спама"""
        from .models import ContactMessage
        
        spam_score = 0
        
        # Проверка частоты запросов
        recent_count = ContactMessage.objects.filter(
            ip_address=contact_message.ip_address,
            created__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_count > 5:
            spam_score += 50
        
        # Проверка на короткие сообщения
        if len(contact_message.message) < 10:
            spam_score += 10
        
        # Проверка на повторяющиеся символы
        if contact_message.message.count('!') > 3 or contact_message.message.count('?') > 3:
            spam_score += 10
        
        # Проверка на спам-слова
        spam_words = ['casino', 'viagra', 'loan', 'credit', 'buy now', 'click here', 'free money']
        message_lower = contact_message.message.lower()
        for word in spam_words:
            if word in message_lower:
                spam_score += 20
        
        # Проверка на подозрительные email
        suspicious_domains = ['temp-mail.org', '10minutemail.com', 'guerrillamail.com']
        email_domain = contact_message.email.split('@')[-1].lower()
        if email_domain in suspicious_domains:
            spam_score += 30
        
        # Проверка на одинаковый текст
        duplicate_count = ContactMessage.objects.filter(
            message=contact_message.message,
            created__gte=timezone.now() - timedelta(days=1)
        ).exclude(id=contact_message.id).count()
        
        if duplicate_count > 0:
            spam_score += 40
        
        # Если счетчик спама больше 70, считаем сообщение спамом
        return spam_score > 70, spam_score

    @staticmethod
    def send_payment_notification(order):
        """Отправка уведомления об оплате заказа"""
        try:
            subject = f'Заказ №{order.order_number} оплачен!'
            
            # HTML шаблон для email
            html_content = render_to_string('home/email/payment_notification.html', {
                'order': order,
                'site_url': settings.SITE_URL
            })
            
            # Текстовый шаблон для email
            text_content = f"""
Заказ №{order.order_number} оплачен!

Клиент: {order.customer_name}
Email: {order.customer_email}
Телефон: {order.customer_phone}
Сумма: {order.total_price} ₽

Дата оплаты: {order.updated.strftime('%d.%m.%Y %H:%M')}

---
Это автоматическое уведомление с сайта {settings.SITE_URL}
            """
            
            # Отправляем email
            email = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.ADMIN_EMAIL]
            )
            email.content_subtype = "html"
            email.send()
            
            # Отправляем уведомление в Telegram
            message_text = f"""
💰 *Заказ оплачен!*

📋 Заказ №{order.order_number}
👤 Клиент: {order.customer_name}
📧 Email: {order.customer_email}
📱 Телефон: {order.customer_phone}
💳 Сумма: {order.total_price} ₽
⏰ Дата: {order.updated.strftime('%d.%m.%Y %H:%M')}

🎉 Можно приступать к работе!
            """
            
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            bot.send_message(
                chat_id=settings.TELEGRAM_CHANNEL_ID,
                text=message_text,
                parse_mode='Markdown'
            )
            
            return True
        except Exception as e:
            print(f"Ошибка отправки уведомления об оплате: {e}")
            return False


class OrderService:
    """Сервис для работы с заказами"""
    
    @staticmethod
    def create_order_from_cart(cart, customer_data):
        """Создание заказа из корзины"""
        from .models import Order, OrderItem
        from django_q.tasks import async_task
        
        with transaction.atomic():
            order = Order.objects.create(
                customer_name=customer_data['name'],
                customer_email=customer_data['email'],
                customer_phone=customer_data['phone'],
                total_price=cart.get_total_price(),
            )
            
            # Копируем элементы корзины в заказ
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    service_type=cart_item.service_type,
                    service_id=cart_item.service_id,
                    title=cart_item.title,
                    price=cart_item.price,
                    quantity=cart_item.quantity
                )
            
            # Фоновая отправка уведомлений
            async_task('home.tasks.send_order_notifications', order.id)
            
            # Очистка корзины
            cart.delete()
            
            logger.info(f"Создан заказ {order.order_number}")
            return order
    
    @staticmethod
    def process_payment(order, payment_data=None):
        """Обработка платежа через YooKassa"""
        from yookassa import Payment
        
        payment = Payment.create({
            "amount": {
                "value": str(order.total_price),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"{settings.SITE_URL}/order/{order.id}/success/"
            },
            "description": f"Заказ {order.order_number}",
            "metadata": {
                "order_id": order.id
            }
        })
        
        order.payment_id = payment.id
        order.save()
        
        logger.info(f"Создан платеж {payment.id} для заказа {order.order_number}")
        return payment