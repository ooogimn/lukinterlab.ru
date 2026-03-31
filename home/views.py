from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import CookieConsent
from django.contrib import messages
from .models import *
from .models import LegalInfo
from Blog.models import *
from .forms import *
from .forms import LegalInfoForm
from django.views.generic import CreateView, ListView, DetailView
from django.conf import settings
from telegram import Bot
import json
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.db import transaction
from yookassa import Payment
from django.urls import reverse
import uuid
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse, reverse_lazy
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
import json
import os
from decimal import Decimal

import requests

from django.core.cache import cache

def home(request):
    # Кэшируем данные главной страницы на 15 минут (900 секунд)
    cache_key_posts = 'home_posts'
    cache_key_otzivs = 'home_otzivs'
    cache_key_rabotas = 'home_rabotas'
    cache_key_services = 'home_services'
    cache_key_extra_services = 'home_extra_services'
    
    # Получаем посты из кэша или БД
    posts = cache.get(cache_key_posts)
    if posts is None:
        posts = list(Post.objects.filter(
            status='published'
        ).exclude(
            slug__isnull=True
        ).exclude(
            slug=''
        ).select_related(
            'author', 'category'
        ).annotate(
            comments_count=Count('comments', filter=Q(comments__active=True))
        ).only(
            'id', 'title', 'slug', 'description', 'kartinka', 
            'created', 'author__username', 'category__title', 'category__slug'
        ).order_by('-created')[:6])
        cache.set(cache_key_posts, posts, 900)
    
    # Получаем отзывы из кэша или БД
    otzivs = cache.get(cache_key_otzivs)
    if otzivs is None:
        otzivs = list(Otziv.objects.filter(
            active=True
        ).only(
            'id', 'name', 'firma', 'foto', 'body', 'created'
        ).order_by('-created')[:6])
        cache.set(cache_key_otzivs, otzivs, 900)
    
    # Получаем работы из БД (кэширование отключено)
    # Берем все работы со статусом 'completed', без ограничений по категориям
    # Увеличиваем лимит до 24, чтобы показать все категории
    rabotas = list(Rabota.objects.filter(
        status='completed'
    ).only(
        'id', 'name', 'category', 'image', 'adres', 'body', 
        'technologies', 'status', 'featured', 'order', 'created', 'updated'
    ).order_by('-featured', '-order', '-created')[:24])
    
    # Логируем для отладки (можно убрать после проверки)
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Загружено работ: {len(rabotas)}, категории: {[r.category for r in rabotas]}")
    # Обрабатываем технологии для каждой работы
    for rabota in rabotas:
        if rabota.technologies:
            rabota.technologies_list = [tech.strip() for tech in rabota.technologies.split(',')]
        else:
            rabota.technologies_list = []
    
    # Получаем услуги из кэша или БД
    services = cache.get(cache_key_services)
    if services is None:
        services = list(Service.objects.filter(
            is_active=True
        ).prefetch_related(
            'extra_services'
        ).only(
            'id', 'title', 'description', 'icon', 'price', 'order', 'is_active'
        ).order_by('order'))
        cache.set(cache_key_services, services, 900)
    
    # Получаем дополнительные услуги из кэша или БД
    standalone_extra_services = cache.get(cache_key_extra_services)
    if standalone_extra_services is None:
        standalone_extra_services = list(StandaloneExtraService.objects.filter(
            is_active=True
        ).only(
            'id', 'title', 'description', 'price', 'order', 'is_active'
        ).order_by('order'))
        cache.set(cache_key_extra_services, standalone_extra_services, 900)
    
    # Получаем правовую информацию для контактов (кэшируем отдельно)
    legal_info_cache_key = 'legal_info_active'
    legal_info_obj = cache.get(legal_info_cache_key)
    if legal_info_obj is None:
        legal_info_obj = LegalInfo.objects.filter(is_active=True).only(
            'id', 'phone', 'email', 'company_name', 'is_active'
        ).first()
        if not legal_info_obj:
            legal_info_obj = LegalInfo()
        # Кэшируем на 1 час (3600 секунд)
        cache.set(legal_info_cache_key, legal_info_obj, 3600)
    
    # Обрабатываем телефон для tel: ссылки (убираем пробелы, скобки, дефисы)
    phone_for_link = legal_info_obj.phone or '+7-905-856-02-82'
    phone_for_link = phone_for_link.replace(' ', '').replace('(', '').replace(')', '').replace('-', '')
    
    page_title = "главная"
    
    return render(request,
                  'home/page_home-1.html',
                  {'otzivs': otzivs,
                   'rabotas': rabotas,
                   'services': services,
                   'standalone_extra_services': standalone_extra_services,
                   'page_title': page_title,
                   'posts': posts,
                   'legal_info': legal_info_obj,
                   'phone_for_link': phone_for_link,
                   })
                   
                   

class OtzivListView(ListView):
    model = Otziv
    template_name = 'otziv/otziv-lil.html'
    context_object_name = 'otzivs'
    # paginate_by = 2

    def get_queryset(self):
        return Otziv.objects.filter(active=True).order_by('-created')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Страница отзывов'
        context['count_otziv'] = self.get_queryset().count()
        return context


class OtzivDetailView(DetailView):
    model = Otziv
    template_name = 'otziv/otziv-detail.html'
    context_object_name = 'otziv'
    
    def get_queryset(self):
        return Otziv.objects.filter(active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        otziv = self.get_object()
        
        # Получаем комментарии с иерархией
        comments = OtzivComment.objects.filter(
            otziv=otziv, 
            active=True, 
            parent=None  # Только корневые комментарии
        ).prefetch_related('children').order_by('-created')
        
        context['comments'] = comments
        context['comment_form'] = OtzivCommentForm()
        context['title'] = f'Отзыв от {otziv.name}'
        return context


class OtzivCreateView(CreateView):
    """создание отзывов на сайте """
    model = Otziv
    template_name = 'otziv/otziv-create.html'
    form_class = OtzivForm  # Исправлено: было OtzivCreateForm
    success_url = '/otziv/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Добавление отзыва'
        return context

    def form_valid(self, form):
        # Сохраняем отзыв без установки author (его нет в модели)
        try:
            form.save()
            print(f"Отзыв успешно сохранен: {form.instance.name}")
        except Exception as e:
            print(f"Ошибка при сохранении отзыва: {e}")
            return self.form_invalid(form)
        return super().form_valid(form)

    def form_invalid(self, form):
        print(f"Форма невалидна: {form.errors}")
        return super().form_invalid(form)


@require_POST
def add_comment_to_otziv(request, otziv_id):
    """Добавление комментария к отзыву"""
    otziv = get_object_or_404(Otziv, id=otziv_id, active=True)
    
    if request.method == 'POST':
        parent_comment_id = request.POST.get('parent_comment_id')
        parent_comment = None
        
        if parent_comment_id:
            parent_comment = get_object_or_404(OtzivComment, id=parent_comment_id, active=True)
        
        form = OtzivCommentForm(request.POST, parent_comment=parent_comment)
        
        if form.is_valid():
            import logging
            logger = logging.getLogger(__name__)
            
            try:
                logger.info(f"[OTZIV_COMMENT] Начало сохранения комментария к отзыву {otziv_id}")
                
                comment = form.save(commit=False)
                comment.otziv = otziv
                comment.parent = parent_comment
                comment.save()
                logger.info(f"[OTZIV_COMMENT] Комментарий {comment.id} сохранен в БД")
                
                # Проверяем, не был ли комментарий удален модерацией
                try:
                    comment.refresh_from_db()
                    logger.info(f"[OTZIV_COMMENT] Комментарий {comment.id} обновлен из БД. Active: {comment.active}")
                except Exception as e:
                    # Комментарий мог быть удален модерацией
                    logger.warning(f"[OTZIV_COMMENT] Комментарий {comment.id} был удален модерацией: {str(e)}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': 'Ваш комментарий был отклонен модерацией за нарушение правил.',
                            'deleted': True
                        }, status=400)
                    else:
                        messages.warning(request, 'Ваш комментарий был отклонен модерацией за нарушение правил.')
                        return redirect(otziv.get_absolute_url())
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    # AJAX запрос - возвращаем JSON с данными нового комментария
                    try:
                        comment_data = {
                            'id': comment.id,
                            'author_name': comment.author_name,
                            'author_company': comment.author_company,
                            'content': comment.content,
                            'created': comment.created.strftime('%d.%m.%Y %H:%M'),
                            'is_admin_reply': comment.is_admin_reply,
                            'parent_id': parent_comment.id if parent_comment else None,
                            'is_reply': parent_comment is not None
                        }
                        logger.info(f"[OTZIV_COMMENT] Формирование JSON ответа для комментария {comment.id}")
                        
                        return JsonResponse({
                            'success': True,
                            'message': 'Комментарий добавлен успешно!',
                            'comment': comment_data
                        })
                    except Exception as e:
                        logger.error(f"[OTZIV_COMMENT] Ошибка при формировании JSON ответа: {str(e)}", exc_info=True)
                        return JsonResponse({
                            'success': False,
                            'message': f'Ошибка при формировании ответа: {str(e)}'
                        }, status=500)
                else:
                    # Обычный POST запрос
                    messages.success(request, 'Комментарий добавлен успешно!')
                    logger.info(f"[OTZIV_COMMENT] Комментарий {comment.id} успешно сохранен (обычный запрос)")
                    return redirect(otziv.get_absolute_url())
            except Exception as e:
                logger.error(f"[OTZIV_COMMENT] КРИТИЧЕСКАЯ ОШИБКА при сохранении комментария: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Произошла ошибка при сохранении комментария: {str(e)}'
                    }, status=500)
                else:
                    messages.error(request, f'Произошла ошибка при сохранении комментария: {str(e)}')
                    return redirect(otziv.get_absolute_url())
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
            else:
                messages.error(request, 'Ошибка при добавлении комментария.')
                return redirect(otziv.get_absolute_url())
    
    return redirect(otziv.get_absolute_url())


def get_comments_for_otziv(request, otziv_id):
    """Получение комментариев для отзыва (для AJAX)"""
    otziv = get_object_or_404(Otziv, id=otziv_id, active=True)
    comments = OtzivComment.objects.filter(
        otziv=otziv, 
        active=True, 
        parent=None
    ).prefetch_related('children').order_by('-created')
    
    comments_data = []
    for comment in comments:
        comment_data = {
            'id': comment.id,
            'author_name': comment.author_name,
            'author_company': comment.author_company,
            'content': comment.content,
            'created': comment.created.strftime('%d.%m.%Y %H:%M'),
            'is_admin_reply': comment.is_admin_reply,
            'children': []
        }
        
        for child in comment.children.filter(active=True).order_by('created'):
            child_data = {
                'id': child.id,
                'author_name': child.author_name,
                'author_company': child.author_company,
                'content': child.content,
                'created': child.created.strftime('%d.%m.%Y %H:%M'),
                'is_admin_reply': child.is_admin_reply,
            }
            comment_data['children'].append(child_data)
        
        comments_data.append(comment_data)
    
    return JsonResponse({'comments': comments_data})


def lead_create(request):
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']
            
            # Send to Telegram
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            chat_id = settings.TELEGRAM_CHANNEL_ID  # or admin chat
            telegram_message = f'Новый лид:\nИмя: {name}\nEmail: {email}\nСообщение: {message}'
            bot.send_message(chat_id=chat_id, text=telegram_message)
            
            return redirect('home:home')  # or success page
    else:
        form = LeadForm()
    
    return render(request, 'home/nabor/contact.html', {'form': form})


from django_ratelimit.decorators import ratelimit

@csrf_exempt
@require_POST
@ratelimit(key='ip', rate='5/m', method='POST')
@ratelimit(key='user_or_ip', rate='20/h', method='POST')
def contact_form(request):
    """Обработка формы контактов"""
    # Проверка блокировки rate limit
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        return JsonResponse({
            'status': 429,
            'message': 'Слишком много запросов. Пожалуйста, попробуйте позже.'
        })
    
    # Проверяем, является ли запрос AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    try:
        # Отладочная информация
        print(f"POST данные: {request.POST}")
        
        # Получаем данные из формы
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()
        attachment = request.FILES.get('attachment')
        
        # Проверка honeypot (защита от спама)
        website = request.POST.get('website', '').strip()
        if website:  # Если honeypot заполнен, это бот
            return JsonResponse({
                'status': 400,
                'message': 'Ошибка отправки сообщения.'
            })
        
        print(f"Полученные данные: name='{name}', email='{email}', message='{message}'")
        
        # Валидация
        if not name or not email or not message:
            return JsonResponse({
                'status': 400,
                'message': 'Пожалуйста, заполните все обязательные поля.'
            })
        
        # Получаем IP адрес и User Agent
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Сохраняем сообщение в базу данных
        try:
            from .models import ContactMessage
            contact_message = ContactMessage.objects.create(
                name=name,
                email=email,
                message=message,
                attachment=attachment,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Трекинг запроса для аналитики
            from .services import SpamProtectionService
            SpamProtectionService.track_request(ip_address, 'contact')
            
            # Проверяем на спам
            is_spam, spam_score = SpamProtectionService.check_spam(contact_message)
            
            if is_spam:
                contact_message.is_spam = True
                contact_message.save()
                print(f"Сообщение отмечено как спам (счетчик: {spam_score})")
                return JsonResponse({
                    'status': 400,
                    'message': 'Ваше сообщение похоже на спам. Пожалуйста, напишите более подробно.'
                })
            
            # Отправляем уведомления через django-Q (фоновая задача)
            from .services import NotificationService
            NotificationService.send_all_notifications(contact_message)
            
        except Exception as db_error:
            print(f"Ошибка сохранения в БД: {db_error}")
            # Продолжаем выполнение даже если БД недоступна
        
        # Логируем сообщение
        print(f"Новое сообщение от {name} ({email}): {message}")
        
        # Если это AJAX запрос, возвращаем JSON
        if is_ajax:
            return JsonResponse({
                'status': 200,
                'message': 'Спасибо! Ваше сообщение отправлено. Мы свяжемся с вами в ближайшее время.'
            })
        else:
            # Для обычного POST запроса показываем сообщение и редиректим
            messages.success(request, 'Спасибо! Ваше сообщение отправлено. Мы свяжемся с вами в ближайшее время.')
            return redirect('home:home')
        
    except Exception as e:
        print(f"Ошибка при обработке формы контактов: {e}")
        if is_ajax:
            return JsonResponse({
                'status': 500,
                'message': 'Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.'
            })
        else:
            messages.error(request, 'Произошла ошибка при отправке сообщения. Пожалуйста, попробуйте позже.')
            return redirect('home:home')


def get_client_ip(request):
    """Получение IP адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class ServiceListView(ListView):
    """Список всех услуг"""
    model = Service
    template_name = 'home/services/service_list.html'
    context_object_name = 'services'
    paginate_by = 12

    def get_queryset(self):
        return Service.objects.filter(is_active=True).prefetch_related('extra_services')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Наши услуги'
        context['standalone_extra_services'] = StandaloneExtraService.objects.filter(is_active=True)
        
        # Добавляем фоны секций
        section_backgrounds = {}
        for section in SectionBackground.objects.filter(is_active=True):
            section_backgrounds[section.section] = section
        context['section_backgrounds'] = section_backgrounds
        
        return context


class ServiceDetailView(DetailView):
    """Детальная страница услуги"""
    model = Service
    template_name = 'home/services/service_detail.html'
    context_object_name = 'service'
    
    def get_queryset(self):
        return Service.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.get_object()
        context['title'] = f'{service.title} - LukInterLab'
        context['related_services'] = Service.objects.filter(is_active=True).exclude(id=service.id)[:3]
        context['standalone_extra_services'] = StandaloneExtraService.objects.filter(is_active=True)
        
        # Добавляем фоны секций
        section_backgrounds = {}
        for section in SectionBackground.objects.filter(is_active=True):
            section_backgrounds[section.section] = section
        context['section_backgrounds'] = section_backgrounds
        
        return context


class StandaloneExtraServiceListView(ListView):
    """Список всех дополнительных услуг"""
    model = StandaloneExtraService
    template_name = 'home/extra_services/extra_service_list.html'
    context_object_name = 'extra_services'
    paginate_by = 12

    def get_queryset(self):
        return StandaloneExtraService.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Дополнительные услуги'
        context['services'] = Service.objects.filter(is_active=True).prefetch_related('extra_services')
        
        # Добавляем фоны секций
        section_backgrounds = {}
        for section in SectionBackground.objects.filter(is_active=True):
            section_backgrounds[section.section] = section
        context['section_backgrounds'] = section_backgrounds
        
        return context


class StandaloneExtraServiceDetailView(DetailView):
    """Детальная страница дополнительной услуги"""
    model = StandaloneExtraService
    template_name = 'home/extra_services/extra_service_detail.html'
    context_object_name = 'extra_service'
    
    def get_queryset(self):
        return StandaloneExtraService.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        extra_service = self.get_object()
        context['title'] = f'{extra_service.title} - LukInterLab'
        context['related_extra_services'] = StandaloneExtraService.objects.filter(is_active=True).exclude(id=extra_service.id)[:3]
        context['services'] = Service.objects.filter(is_active=True).prefetch_related('extra_services')
        
        # Добавляем фоны секций
        section_backgrounds = {}
        for section in SectionBackground.objects.filter(is_active=True):
            section_backgrounds[section.section] = section
        context['section_backgrounds'] = section_backgrounds
        
        return context


def get_or_create_cart(request):
    """Получить или создать корзину для текущей сессии"""
    if not request.session.session_key:
        request.session.create()
    
    cart, created = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def add_to_cart(request):
    """Добавить услугу в корзину"""
    if request.method == 'POST':
        form = AddToCartForm(request.POST)
        if form.is_valid():
            service_type = form.cleaned_data['service_type']
            service_id = form.cleaned_data['service_id']
            quantity = form.cleaned_data['quantity']
            
            # Получаем информацию об услуге
            if service_type == 'service':
                try:
                    service = Service.objects.get(id=service_id, is_active=True)
                    title = service.title
                    price = service.price
                except Service.DoesNotExist:
                    return JsonResponse({'success': False, 'message': 'Услуга не найдена'})
            elif service_type == 'extra_service':
                try:
                    service = StandaloneExtraService.objects.get(id=service_id, is_active=True)
                    title = service.title
                    price = service.price
                except StandaloneExtraService.DoesNotExist:
                    return JsonResponse({'success': False, 'message': 'Дополнительная услуга не найдена'})
            elif service_type == 'standalone_extra_service':
                try:
                    service = StandaloneExtraService.objects.get(id=service_id, is_active=True)
                    title = service.title
                    price = service.price
                except StandaloneExtraService.DoesNotExist:
                    return JsonResponse({'success': False, 'message': 'Дополнительная услуга не найдена'})
            else:
                return JsonResponse({'success': False, 'message': 'Неверный тип услуги'})
            
            # Получаем или создаем корзину
            cart = get_or_create_cart(request)
            
            # Нормализуем тип услуги для корзины
            cart_service_type = 'extra_service' if service_type == 'standalone_extra_service' else service_type
            
            # Добавляем или обновляем элемент корзины
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                service_type=cart_service_type,
                service_id=service_id,
                defaults={
                    'title': title,
                    'price': price,
                    'quantity': quantity
                }
            )
            
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Услуга "{title}" добавлена в корзину',
                'cart_count': cart.get_items_count()
            })
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})


def cart_view(request):
    """Просмотр корзины"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'total_price': cart.get_total_price(),
    }
    
    return render(request, 'home/cart/cart.html', context)


def update_cart_item(request, item_id):
    """Обновить количество товара в корзине"""
    if request.method == 'POST':
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__session_key=request.session.session_key)
            cart = cart_item.cart  # Сохраняем ссылку на корзину
            quantity = int(request.POST.get('quantity', 1))
            
            if quantity > 0:
                cart_item.quantity = quantity
                cart_item.save()
            else:
                cart_item.delete()
            
            # Обновляем корзину из БД для получения актуальных данных
            cart.refresh_from_db()
                
            return JsonResponse({
                'success': True,
                'total_price': cart.get_total_price(),
                'cart_count': cart.get_items_count()
            })
        except CartItem.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Элемент корзины не найден'})
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})


def remove_from_cart(request, item_id):
    """Удалить товар из корзины"""
    if request.method == 'POST':
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__session_key=request.session.session_key)
            cart = cart_item.cart  # Сохраняем ссылку на корзину перед удалением
            cart_item.delete()
            
            # Обновляем корзину из БД для получения актуальных данных
            cart.refresh_from_db()
            
            return JsonResponse({
                'success': True,
                'total_price': cart.get_total_price(),
                'cart_count': cart.get_items_count()
            })
        except CartItem.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Элемент корзины не найден'})
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})


def checkout(request):
    """Оформление заказа"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.all()
    
    if not cart_items.exists():
        messages.warning(request, 'Ваша корзина пуста.')
        return redirect('home:cart')
    
    if request.method == 'POST':
        print(f"DEBUG: POST request received")
        print(f"DEBUG: POST data: {request.POST}")
        print(f"DEBUG: Create account value: {request.POST.get('create_account')}")
        
        order_form = OrderForm(request.POST)
        
        print(f"DEBUG: Form is valid: {order_form.is_valid()}")
        if not order_form.is_valid():
            print(f"DEBUG: Form errors: {order_form.errors}")
            print(f"DEBUG: Form errors as JSON: {order_form.errors.as_json()}")
            # Добавляем сообщения об ошибках для пользователя
            for field, errors in order_form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        
        if order_form.is_valid():
            print(f"DEBUG: Creating order...")
            # Создаем заказ
            order = order_form.save(total_price=cart.get_total_price())
            print(f"DEBUG: Order created with ID: {order.id}")
            
            # Добавляем товары из корзины в заказ
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    service_type=item.service_type,
                    service_id=item.service_id,
                    title=item.title,
                    price=item.price,
                    quantity=item.quantity
                )
            
            # Очищаем корзину
            cart.delete()
            
            # Если создан аккаунт, авторизуем пользователя
            if order.customer and order.customer.user:
                login(request, order.customer.user)
                messages.success(request, f'Заказ оформлен! Аккаунт создан. Добро пожаловать в личный кабинет, {order.customer.user.get_full_name() or order.customer.user.username}!')
            else:
                messages.success(request, 'Заказ оформлен! Мы свяжемся с вами в ближайшее время.')
            
            # Перенаправляем на опросный лист
            return redirect('home:order_questionnaire', order_id=order.id)
    else:
        order_form = OrderForm()
    
    context = {
        'order_form': order_form,
        'cart_items': cart_items,
        'total_price': cart.get_total_price(),
    }
    
    return render(request, 'home/checkout/checkout.html', context)


def order_questionnaire(request, order_id):
    """Заполнение опросного листа заказа"""
    order = get_object_or_404(Order, id=order_id)
    
    # Если пользователь не авторизован, но у заказа есть заказчик, авторизуем его
    if not request.user.is_authenticated and order.customer and order.customer.user:
        login(request, order.customer.user)
    
    if request.method == 'POST':
        questionnaire_form = OrderQuestionnaireForm(request.POST)
        file_form = OrderFileForm(request.POST, request.FILES)
        
        if questionnaire_form.is_valid():
            # Сохраняем опросный лист
            questionnaire = questionnaire_form.save(commit=False)
            questionnaire.order = order
            questionnaire.save()
            
            # Сохраняем файлы (если они есть)
            files = request.FILES.getlist('file')
            additional_files = request.FILES.getlist('additional_files')
            
            # Обрабатываем основной файл
            if files and files[0]:
                OrderFile.objects.create(
                    order=order,
                    file=files[0],
                    filename=files[0].name,
                    description=request.POST.get('description', '')
                )
            
            # Обрабатываем дополнительные файлы
            for file in additional_files:
                if file:
                    OrderFile.objects.create(
                        order=order,
                        file=file,
                        filename=file.name,
                        description='Дополнительный файл'
                    )
            
            # Если у заказа есть заказчик, перенаправляем в личный кабинет
            if order.customer and order.customer.user:
                messages.success(request, 'Заказ успешно оформлен! Переходим в личный кабинет.')
                return redirect('home:customer_dashboard')
            else:
                messages.success(request, 'Заказ успешно оформлен! Мы свяжемся с вами в ближайшее время.')
                return redirect('home:order_success', order_id=order.id)
    else:
        questionnaire_form = OrderQuestionnaireForm()
        file_form = OrderFileForm()
    
    context = {
        'order': order,
        'questionnaire_form': questionnaire_form,
        'file_form': file_form,
    }
    
    return render(request, 'home/checkout/questionnaire.html', context)


def order_success(request, order_id):
    """Страница успешного оформления заказа"""
    order = get_object_or_404(Order, id=order_id)
    
    context = {
        'order': order,
    }
    
    return render(request, 'home/checkout/success.html', context)


def order_detail(request, order_id):
    """Детальная страница заказа"""
    order = get_object_or_404(Order, id=order_id)
    
    context = {
        'order': order,
    }
    
    return render(request, 'home/orders/order_detail.html', context)


def pay_order(request, order_id):
    """Страница оплаты заказа через YooKassa"""
    order = get_object_or_404(Order, id=order_id)
    
    # Если заказ уже оплачен, перенаправляем на страницу успеха
    if order.payment_status == 'paid':
        messages.info(request, 'Этот заказ уже оплачен')
        return redirect('home:order_success', order_id=order.id)
    

    
    if request.method == 'POST':
        try:
            # Создаем платеж в YooKassa
            payment = Payment.create({
                "amount": {
                    "value": str(order.total_price),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": request.build_absolute_uri(
                        reverse('home:order_success', args=[order.id])
                    )
                },
                "capture": True,
                "description": f"Оплата заказа №{order.order_number} - LukInterLab",
                "metadata": {
                    "order_id": str(order.id),
                    "order_number": order.order_number
                }
            }, settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)
            
            # Сохраняем ID платежа в заказе
            order.payment_id = payment.id
            order.save()
            
            # Перенаправляем на страницу оплаты YooKassa
            return redirect(payment.confirmation.confirmation_url)
            
        except Exception as e:
            messages.error(request, f'Ошибка при создании платежа: {str(e)}')
            return redirect('home:order_detail', order_id=order.id)
    
    context = {
        'order': order,
        'title': f'Оплата заказа №{order.order_number}'
    }
    return render(request, 'home/checkout/pay.html', context)


@csrf_exempt
def yookassa_webhook(request):
    """Webhook для обработки уведомлений от YooKassa"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Получаем данные от YooKassa
        data = json.loads(request.body)
        
        # Проверяем, что это уведомление о платеже
        if 'object' in data and data['object']['type'] == 'payment':
            payment_data = data['object']
            payment_id = payment_data['id']
            
            # Находим заказ по ID платежа
            try:
                order = Order.objects.get(payment_id=payment_id)
                
                # Обновляем статус заказа в зависимости от статуса платежа
                if payment_data['status'] == 'succeeded':
                    order.payment_status = 'paid'
                    order.status = 'confirmed'
                    order.save()
                    
                    # Отправляем уведомление администратору
                    try:
                        from .services import NotificationService
                        NotificationService.send_payment_notification(order)
                    except Exception as e:
                        print(f"Ошибка отправки уведомления об оплате: {e}")
                    
                elif payment_data['status'] == 'canceled':
                    order.payment_status = 'failed'
                    order.save()
                
                return JsonResponse({'status': 'success'})
                
            except Order.DoesNotExist:
                return JsonResponse({'error': 'Order not found'}, status=404)
        
        return JsonResponse({'error': 'Invalid webhook data'}, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def payment_success(request, order_id):
    """Страница успешной оплаты"""
    order = get_object_or_404(Order, id=order_id)
    
    # Проверяем статус платежа через API YooKassa
    if order.payment_id and order.payment_status == 'pending':
        try:
            payment = Payment.find_one(order.payment_id, settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)
            if payment.status == 'succeeded':
                order.payment_status = 'paid'
                order.status = 'confirmed'
                order.save()
                messages.success(request, 'Оплата прошла успешно!')
            elif payment.status == 'canceled':
                order.payment_status = 'failed'
                order.save()
                messages.error(request, 'Платеж был отменен')
        except Exception as e:
            print(f"Ошибка проверки статуса платежа: {e}")
    
    context = {
        'order': order,
        'title': f'Заказ №{order.order_number} - Оплата'
    }
    return render(request, 'home/checkout/payment_success.html', context)

# ==================== ЛИЧНЫЙ КАБИНЕТ ====================

def customer_register(request):
    """Регистрация заказчика"""
    if request.user.is_authenticated:
        return redirect('home:customer_dashboard')
    
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать в личный кабинет.')
            return redirect('home:customer_dashboard')
    else:
        form = CustomerRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Регистрация'
    }
    return render(request, 'home/customer/register.html', context)


def customer_login(request):
    """Вход в личный кабинет"""
    if request.user.is_authenticated:
        return redirect('home:customer_dashboard')
    
    if request.method == 'POST':
        form = CustomerLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.get_full_name() or user.username}!')
                return redirect('home:customer_dashboard')
    else:
        form = CustomerLoginForm()
    
    context = {
        'form': form,
        'title': 'Вход в личный кабинет'
    }
    return render(request, 'home/customer/login.html', context)


@require_POST
def customer_vkid_complete(request):
    """Приём access_token после VK ID SDK → проверка через id.vk.ru → вход в личный кабинет."""
    if not getattr(settings, 'VKID_APP_ID', None):
        return JsonResponse({'error': 'vkid_disabled'}, status=503)
    try:
        payload = json.loads(request.body.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_json'}, status=400)

    access_token = payload.get('access_token')
    if not access_token:
        return JsonResponse({'error': 'missing_token'}, status=400)

    try:
        r = requests.post(
            'https://id.vk.ru/oauth2/user_info',
            data={
                'client_id': str(settings.VKID_APP_ID),
                'access_token': access_token,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=15,
        )
    except requests.RequestException:
        return JsonResponse({'error': 'vk_unreachable'}, status=502)

    try:
        body = r.json()
    except ValueError:
        return JsonResponse({'error': 'invalid_vk_response'}, status=502)

    if r.status_code != 200 or 'error' in body:
        return JsonResponse({
            'error': body.get('error', 'vk_error'),
            'detail': body.get('error_description', ''),
        }, status=400)

    user_info = body.get('user') or {}
    vk_user_id = user_info.get('user_id')
    if vk_user_id is None:
        return JsonResponse({'error': 'no_user'}, status=400)

    vk_user_id = str(vk_user_id)
    username = f'vkid_{vk_user_id}'
    first_name = (user_info.get('first_name') or '')[:30]
    last_name = (user_info.get('last_name') or '')[:30]
    email_from_vk = user_info.get('email')
    placeholder_email = f'vkid_{vk_user_id}@vkid.invalid'
    email = email_from_vk or placeholder_email
    if email_from_vk and User.objects.filter(email=email_from_vk).exclude(username=username).exists():
        email = placeholder_email

    with transaction.atomic():
        try:
            user = User.objects.get(username=username)
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.set_unusable_password()
            if email_from_vk and not User.objects.filter(email=email_from_vk).exclude(pk=user.pk).exists():
                user.email = email_from_vk
            user.save()
        except User.DoesNotExist:
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            user.set_unusable_password()
            user.save()

        Customer.objects.get_or_create(user=user, defaults={'phone': ''})

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(
        request,
        f'Добро пожаловать, {user.get_full_name() or user.username}!',
    )
    return JsonResponse({'ok': True, 'redirect': reverse('home:customer_dashboard')})


@login_required
def customer_logout(request):
    """Выход из личного кабинета"""
    logout(request)
    messages.success(request, 'Вы успешно вышли из личного кабинета.')
    return redirect('home:home')


@login_required
def customer_dashboard(request):
    """Главная страница личного кабинета"""
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        # Если у пользователя нет профиля заказчика, создаем его
        customer = Customer.objects.create(
            user=request.user,
            phone=request.user.email  # Временно используем email как телефон
        )
    
    # Получаем заказы пользователя
    orders = Order.objects.filter(customer=customer).order_by('-created')
    
    # Статистика
    total_orders = orders.count()
    pending_payment_orders = orders.filter(payment_status='pending').count()
    completed_orders = orders.filter(status='completed').count()
    total_spent = sum(order.total_price for order in orders.filter(payment_status='paid'))
    
    context = {
        'customer': customer,
        'orders': orders[:5],  # Последние 5 заказов
        'total_orders': total_orders,
        'pending_payment_orders': pending_payment_orders,
        'completed_orders': completed_orders,
        'total_spent': total_spent,
        'title': 'Личный кабинет'
    }
    return render(request, 'home/customer/dashboard.html', context)


@login_required
def customer_profile(request):
    """Личный кабинет заказчика"""
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        customer = Customer.objects.create(user=request.user)
    
    # Получаем заказы пользователя
    orders = Order.objects.filter(customer=customer).order_by('-created')
    
    context = {
        'customer': customer,
        'orders': orders,
        'title': 'Личный кабинет'
    }
    return render(request, 'home/customer/profile.html', context)


@login_required
def customer_edit_profile(request):
    """Редактирование профиля заказчика"""
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        customer = Customer.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=customer, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('home:customer_profile')
    else:
        form = CustomerProfileForm(instance=customer, user=request.user)
    
    context = {
        'form': form,
        'customer': customer,
        'title': 'Редактирование профиля'
    }
    
    return render(request, 'home/customer/edit_profile.html', context)


@login_required
def customer_orders(request):
    """Список заказов пользователя"""
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        customer = Customer.objects.create(user=request.user)
    
    orders = Order.objects.filter(customer=customer).order_by('-created')
    
    # Фильтрация
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Пагинация
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'customer': customer,
        'status_filter': status_filter,
        'title': 'Мои заказы'
    }
    return render(request, 'home/customer/orders.html', context)


@login_required
def customer_order_detail(request, order_id):
    """Детальная страница заказа пользователя"""
    try:
        customer = request.user.customer
    except Customer.DoesNotExist:
        customer = Customer.objects.create(user=request.user)
    
    order = get_object_or_404(Order, id=order_id, customer=customer)
    
    if request.method == 'POST':
        comment_form = OrderCommentForm(request.POST, user=request.user, order=order, is_admin=False)
        if comment_form.is_valid():
            comment_form.save()
            messages.success(request, 'Комментарий добавлен!')
            return redirect('home:customer_order_detail', order_id=order.id)
    else:
        comment_form = OrderCommentForm(user=request.user, order=order, is_admin=False)
    
    context = {
        'order': order,
        'comment_form': comment_form,
        'customer': customer,
        'title': f'Заказ №{order.order_number}'
    }
    return render(request, 'home/customer/order_detail.html', context)


# ==================== АДМИН ПАНЕЛЬ ДЛЯ ЗАКАЗОВ ====================

@staff_member_required
def admin_orders(request):
    """Список всех заказов для администратора"""
    orders = Order.objects.all().order_by('-created')
    
    # Фильтрация
    status_filter = request.GET.get('status')
    payment_filter = request.GET.get('payment_status')
    search = request.GET.get('search')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    if payment_filter:
        orders = orders.filter(payment_status=payment_filter)
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(customer_email__icontains=search)
        )
    
    # Пагинация
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Статистика
    total_orders = Order.objects.count()
    new_orders = Order.objects.filter(status='new').count()
    paid_orders = Order.objects.filter(payment_status='paid').count()
    total_revenue = sum(order.total_price for order in Order.objects.filter(payment_status='paid'))
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'search': search,
        'total_orders': total_orders,
        'new_orders': new_orders,
        'paid_orders': paid_orders,
        'total_revenue': total_revenue,
        'title': 'Управление заказами'
    }
    return render(request, 'home/admin/orders.html', context)


@staff_member_required
def admin_order_detail(request, order_id):
    """Детальная страница заказа для администратора"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        # Обработка изменения статуса
        new_status = request.POST.get('status')
        new_payment_status = request.POST.get('payment_status')
        
        if new_status and new_status != order.status:
            order.status = new_status
            order.save()
            messages.success(request, f'Статус заказа изменен на "{order.get_status_display()}"')
        
        if new_payment_status and new_payment_status != order.payment_status:
            order.payment_status = new_payment_status
            order.save()
            messages.success(request, f'Статус оплаты изменен на "{order.get_payment_status_display()}"')
        
        # Обработка комментария
        comment_form = OrderCommentForm(request.POST, user=request.user, order=order, is_admin=True)
        if comment_form.is_valid():
            comment_form.save()
            messages.success(request, 'Комментарий добавлен!')
            return redirect('home:admin_order_detail', order_id=order.id)
    else:
        comment_form = OrderCommentForm(user=request.user, order=order, is_admin=True)
    
    context = {
        'order': order,
        'comment_form': comment_form,
        'title': f'Заказ №{order.order_number}'
    }
    return render(request, 'home/admin/order_detail.html', context)


@require_POST
def cookie_consent(request):
    """Сохранение согласия пользователя на cookie"""
    try:
        # Создаем сессию если её нет
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        ip_address = request.META.get('REMOTE_ADDR')
        
        analytics = request.POST.get('analytics', 'false') == 'true'
        marketing = request.POST.get('marketing', 'false') == 'true'
        
        # Сохраняем в БД
        CookieConsent.objects.update_or_create(
            session_key=session_key,
            defaults={
                'ip_address': ip_address,
                'essential_cookies': True,
                'analytics_cookies': analytics,
                'marketing_cookies': marketing,
                'consent_given': True,
            }
        )
        
        # Устанавливаем cookie о согласии (срок 1 год)
        response = JsonResponse({'status': 'success', 'message': 'Настройки сохранены'})
        response.set_cookie(
            'cookie_consent', 
            'accepted', 
            max_age=365*24*60*60,
            httponly=False,  # Доступен для JavaScript
            samesite='Lax'
        )
        
        return response
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Cookie consent error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def legal_info(request):
    """Страница правовой информации"""
    legal_info_obj = LegalInfo.objects.filter(is_active=True).first()
    
    # Если нет активной записи, создаём пустую для отображения
    if not legal_info_obj:
        legal_info_obj = LegalInfo()
    
    context = {
        'legal_info': legal_info_obj,
        'page_title': 'Правовая информация',
        'user': request.user,  # Явно передаём user в контекст
    }
    
    return render(request, 'home/legal_info.html', context)


def privacy_policy(request):
    """Страница политики конфиденциальности"""
    legal_info_obj = LegalInfo.objects.filter(is_active=True).first()
    
    # Если нет активной записи, создаём пустую для отображения
    if not legal_info_obj:
        legal_info_obj = LegalInfo()
    
    context = {
        'legal_info': legal_info_obj,
        'page_title': 'Политика конфиденциальности',
        'user': request.user,  # Явно передаём user в контекст
    }
    
    return render(request, 'home/privacy_policy.html', context)


@login_required
def edit_legal_info(request):
    """Редактирование правовой информации (только для суперпользователя)"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    legal_info_obj = LegalInfo.objects.filter(is_active=True).first()
    
    if not legal_info_obj:
        legal_info_obj = LegalInfo.objects.create(is_active=True)
    
    if request.method == 'POST':
        # Создаём копию POST данных для безопасного обновления
        post_data = request.POST.copy()
        
        # Если некоторые поля не переданы, используем существующие значения
        for field in ['company_name', 'company_full_name', 'inn', 'kpp', 'ogrn', 
                      'legal_address', 'actual_address', 'phone', 'email', 'website',
                      'bank_name', 'bank_account', 'correspondent_account', 'bik',
                      'about_site', 'about_company', 'terms_of_use', 'privacy_policy']:
            if field not in post_data or not post_data[field]:
                if hasattr(legal_info_obj, field):
                    post_data[field] = getattr(legal_info_obj, field) or ''
        
        form = LegalInfoForm(post_data, request.FILES, instance=legal_info_obj)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Информация успешно сохранена'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    # GET запрос - возвращаем форму
    form = LegalInfoForm(instance=legal_info_obj)
    
    # Рендерим форму в HTML
    form_html = render_to_string('home/partials/legal_info_form.html', {
        'form': form,
        'legal_info': legal_info_obj
    }, request=request)
    
    return JsonResponse({'form_html': form_html})

# ==================== ПОРТФОЛИО ДАШБОРД ====================
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from .forms import RabotaForm

class PortfolioDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Rabota
    template_name = 'home/portfolio_dashboard.html'
    context_object_name = 'rabotas'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

class RabotaCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Rabota
    form_class = RabotaForm
    template_name = 'home/rabota_form.html'
    success_url = reverse_lazy('home:portfolio_dashboard')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def form_valid(self, form):
        response = super().form_valid(form)
        from .models import RabotaMedia
        # Обработка загрузки новых медиа
        files = self.request.FILES.getlist('new_media')
        for f in files:
            RabotaMedia.objects.create(rabota=self.object, file=f)
            
        messages.success(self.request, "Проект успешно добавлен в портфолио!")
        return response

class RabotaUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Rabota
    form_class = RabotaForm
    template_name = 'home/rabota_form.html'
    success_url = reverse_lazy('home:portfolio_dashboard')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
        
    def form_valid(self, form):
        response = super().form_valid(form)
        from .models import RabotaMedia
        
        # Удаление выбранных медиафайлов
        delete_media_ids = self.request.POST.getlist('delete_media')
        if delete_media_ids:
            RabotaMedia.objects.filter(id__in=delete_media_ids, rabota=self.object).delete()
            
        # Загрузка новых медиафайлов
        files = self.request.FILES.getlist('new_media')
        for f in files:
            RabotaMedia.objects.create(rabota=self.object, file=f)
            
        messages.success(self.request, "Проект успешно обновлен!")
        return response
    
    def form_valid(self, form):
        messages.success(self.request, "Проект успешно обновлен!")
        return super().form_valid(form)

