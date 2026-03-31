import json
import time
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from django.db import OperationalError
from .models import ChatSession, ChatMessage, AssistantKnowledge, AssistantSettings
from .ai_service import AIService
from .telegram_service import TelegramService
import logging

logger = logging.getLogger(__name__)



def get_assistant_settings_safe(max_retries=3, retry_delay=0.1):
    """
    Безопасное получение настроек ассистента с обработкой блокировок базы данных
    
    Args:
        max_retries: Максимальное количество попыток
        retry_delay: Начальная задержка между попытками (секунды)
    
    Returns:
        AssistantSettings объект или None
    """
    for attempt in range(max_retries):
        try:
            return AssistantSettings.objects.first()
        except OperationalError as e:
            error_msg = str(e).lower()
            if 'database is locked' in error_msg or 'locked' in error_msg:
                if attempt < max_retries - 1:
                    # Экспоненциальная задержка перед повторной попыткой
                    time.sleep(retry_delay * (2 ** attempt))
                    logger.warning(f"Database locked when getting settings, retry {attempt + 1}/{max_retries}")
                    continue
                else:
                    logger.error(f"Failed to get settings after {max_retries} attempts: database is locked")
                    return None
            else:
                # Другие ошибки базы данных
                logger.error(f"Database error when getting settings: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Error getting settings: {str(e)}")
            return None
    
    return None


"""API для чата с AI-ассистентом"""
class ChatAPIView(View):
    """API для чата с AI-ассистентом"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Получить историю сообщений сессии"""
        session_id = request.GET.get('session_id')
        if not session_id:
            return JsonResponse({'error': 'Session ID required'}, status=400)
        
        try:
            session = ChatSession.objects.get(session_id=session_id)
            messages = session.messages.all()[:50]  # Последние 50 сообщений
            
            messages_data = []
            for msg in messages:
                messages_data.append({
                    'id': str(msg.id),
                    'type': msg.message_type,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'tokens_used': msg.tokens_used,
                    'response_time': msg.response_time
                })
            
            return JsonResponse({
                'session_id': session_id,
                'messages': messages_data,
                'is_active': session.is_active
            })
            
        except ChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)
    
    def post(self, request):
        """Отправить сообщение и получить ответ от AI"""
        try:
            data = json.loads(request.body)
            message = data.get('message', '').strip()
            session_id = data.get('session_id')
            page_url = data.get('page_url', '')
            
            if not message:
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Получаем или создаем сессию
            session = self._get_or_create_session(request, session_id, page_url)
            
            # Проверяем лимиты
            if not self._check_limits(session):
                return JsonResponse({'error': 'Session limit exceeded'}, status=429)
            
            # Сохраняем сообщение пользователя
            user_message = ChatMessage.objects.create(
                session=session,
                message_type='user',
                content=message
            )
            
            # Отправляем уведомление в Telegram (если включено)
            self._send_telegram_notification(session, message, request.user)
            
            # Получаем ответ от AI
            start_time = time.time()
            ai_response = self._get_ai_response(session, message)
            response_time = time.time() - start_time
            
            # Сохраняем ответ AI
            ai_message = ChatMessage.objects.create(
                session=session,
                message_type='assistant',
                content=ai_response['content'],
                tokens_used=ai_response.get('tokens_used', 0),
                response_time=response_time,
                model_used=ai_response.get('model', '')
            )
            
            return JsonResponse({
                'message_id': str(ai_message.id),
                'content': ai_response['content'],
                'timestamp': ai_message.timestamp.isoformat(),
                'tokens_used': ai_response.get('tokens_used', 0),
                'response_time': response_time,
                'session_id': session.session_id
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Chat API error: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    def _get_or_create_session(self, request, session_id=None, page_url=''):
        """Получить существующую сессию или создать новую"""
        if session_id:
            try:
                return ChatSession.objects.get(session_id=session_id)
            except ChatSession.DoesNotExist:
                pass
        
        # Создаем новую сессию
        new_session_id = str(uuid.uuid4())
        user = request.user if request.user.is_authenticated else None
        
        session = ChatSession.objects.create(
            session_id=new_session_id,
            user=user,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            page_url=page_url,
            referrer=request.META.get('HTTP_REFERER', '')
        )
        
        # Отправляем приветственное сообщение
        settings = get_assistant_settings_safe()
        if settings and settings.is_enabled:
            welcome_content = self._generate_welcome_message(settings, user)
            welcome_msg = ChatMessage.objects.create(
                session=session,
                message_type='assistant',
                content=welcome_content
            )
        
        return session
    
    def _get_client_ip(self, request):
        """Получить IP адрес клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _check_limits(self, session):
        """Проверить лимиты сессии"""
        settings = get_assistant_settings_safe()
        if not settings:
            return True
        
        # Проверяем количество сообщений
        message_count = session.messages.count()
        if message_count >= settings.max_messages_per_session:
            return False
        
        # Проверяем время сессии
        if session.created_at:
            time_diff = timezone.now() - session.created_at
            if time_diff.total_seconds() > settings.session_timeout * 60:
                session.is_active = False
                session.save()
                return False
        
        return True
    
    def _get_ai_response(self, session, message):
        """Получить ответ от AI"""
        try:
            # Получаем контекст из базы знаний
            context = self._get_relevant_context(message)
            
            # Получаем историю сообщений для контекста
            recent_messages = list(session.messages.all())[-10:]  # Последние 10 сообщений
            conversation_history = []
            for msg in recent_messages:
                conversation_history.append({
                    'role': 'user' if msg.message_type == 'user' else 'assistant',
                    'content': msg.content
                })
            
            # Используем AI сервис с настройками
            settings = get_assistant_settings_safe()
            ai_service = AIService(settings)
            response = ai_service.generate_response(
                message=message,
                context=context,
                conversation_history=conversation_history
            )
            
            return response
            
        except Exception as e:
            logger.error(f"AI response error: {str(e)}")
            return {
                'content': 'Извините, произошла ошибка. Попробуйте еще раз или обратитесь к администратору.',
                'tokens_used': 0,
                'model': 'error'
            }
    
    def _get_relevant_context(self, message):
        """Получить релевантный контекст из базы знаний"""
        # Простой поиск по ключевым словам
        keywords = message.lower().split()
        relevant_knowledge = AssistantKnowledge.objects.filter(
            is_active=True
        ).filter(
            Q(keywords__icontains=message) | 
            Q(title__icontains=message) |
            Q(content__icontains=message)
        ).order_by('-priority')[:5]
        
        context = []
        for knowledge in relevant_knowledge:
            context.append({
                'title': knowledge.title,
                'content': knowledge.content,
                'category': knowledge.category
            })
        
        return context
    
    def _generate_welcome_message(self, settings: AssistantSettings, user=None) -> str:
        """Генерировать персонализированное приветственное сообщение"""
        template = settings.welcome_message_template
        
        # Заменяем плейсхолдеры
        message = template.format(
            name=settings.assistant_name,
            username=user.get_full_name() if user and user.get_full_name() else 
                   (user.username if user else None)
        )
        
        # Если персонализация отключена или пользователь не авторизован
        if not settings.use_personalized_greeting or not user:
            # Убираем упоминание имени пользователя
            message = message.replace('{username}', '').replace('Доброго дня! ', 'Доброго дня!')
        
        return message
    
    def _send_telegram_notification(self, session: ChatSession, message: str, user=None):
        """Отправить уведомление в Telegram"""
        try:
            settings = get_assistant_settings_safe()
            if not settings or not settings.enable_telegram_notifications:
                return
            
            telegram_service = TelegramService(settings)
            
            # Определяем имя пользователя
            username = None
            if user and user.is_authenticated:
                username = user.get_full_name() or user.username
            
            # Отправляем уведомление
            telegram_service.send_notification(session, message, username)
            
        except Exception as e:
            logger.error(f"Error sending telegram notification: {str(e)}")


"""API для обратной связи по сообщениям"""
@csrf_exempt
@require_http_methods(["POST"])
def feedback_api(request):
    """API для обратной связи по сообщениям"""
    try:
        data = json.loads(request.body)
        message_id = data.get('message_id')
        is_helpful = data.get('is_helpful')
        feedback_text = data.get('feedback', '')
        
        if not message_id:
            return JsonResponse({'error': 'Message ID required'}, status=400)
        
        try:
            message = ChatMessage.objects.get(id=message_id)
            message.is_helpful = is_helpful
            message.user_feedback = feedback_text
            message.save()
            
            return JsonResponse({'status': 'success'})
            
        except ChatMessage.DoesNotExist:
            return JsonResponse({'error': 'Message not found'}, status=404)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Feedback API error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


"""API для получения аналитики чата"""
@csrf_exempt
@require_http_methods(["GET"])
def analytics_api(request):
    """API для получения аналитики чата"""
    try:
        # Простая аналитика за последние 7 дней
        from datetime import datetime, timedelta
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        sessions = ChatSession.objects.filter(created_at__date__range=[start_date, end_date])
        messages = ChatMessage.objects.filter(session__in=sessions)
        
        analytics = {
            'total_sessions': sessions.count(),
            'total_messages': messages.count(),
            'unique_users': sessions.values('ip_address').distinct().count(),
            'avg_response_time': messages.filter(message_type='assistant').aggregate(
                avg_time=models.Avg('response_time')
            )['avg_time'] or 0,
            'satisfaction_rate': messages.filter(is_helpful=True).count() / max(messages.count(), 1) * 100
        }
        
        return JsonResponse(analytics)
        
    except Exception as e:
        logger.error(f"Analytics API error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


"""API для получения настроек ассистента"""
@csrf_exempt
@require_http_methods(["GET"])
def settings_api(request):
    """API для получения настроек ассистента"""
    try:
        settings = get_assistant_settings_safe()
        if not settings:
            return JsonResponse({
                'is_enabled': False,
                'welcome_message': 'Ассистент не настроен',
                'auto_start': False,
                'show_typing_indicator': True,
                'theme_color': '#667eea',
                'position': 'bottom-right'
            })
        
        return JsonResponse({
            'is_enabled': settings.is_enabled,
            'welcome_message': settings.welcome_message,
            'auto_start': settings.auto_start,
            'auto_start_delay': settings.auto_start_delay,
            'assistant_name': settings.assistant_name,
            'welcome_message_template': settings.welcome_message_template,
            'use_personalized_greeting': settings.use_personalized_greeting,
            'show_typing_indicator': settings.show_typing_indicator,
            'theme_color': settings.theme_color,
            'position': settings.position,
            'max_messages_per_session': settings.max_messages_per_session,
            'session_timeout': settings.session_timeout,
            'enable_telegram_notifications': settings.enable_telegram_notifications,
            'enable_admin_takeover': settings.enable_admin_takeover
        })
        
    except Exception as e:
        logger.error(f"Settings API error: {str(e)}")
        return JsonResponse({
            'error': 'Database temporarily unavailable',
            'is_enabled': False,
            'welcome_message': 'Ассистент временно недоступен',
            'auto_start': False,
            'show_typing_indicator': True,
            'theme_color': '#667eea',
            'position': 'bottom-right'
        }, status=503)


"""Webhook для получения обновлений от Telegram"""
@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    """Webhook для получения обновлений от Telegram"""
    try:
        from .telegram_service import TelegramWebhookHandler
        
        settings = get_assistant_settings_safe()
        if not settings or not settings.enable_telegram_notifications:
            return JsonResponse({'status': 'disabled'})
        
        update_data = json.loads(request.body)
        handler = TelegramWebhookHandler(settings)
        result = handler.handle_update(update_data)
        
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Telegram webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


"""API для получения новых сообщений в сессии"""
@csrf_exempt
@require_http_methods(["GET"])
def get_new_messages_api(request):
    """API для получения новых сообщений в сессии"""
    try:
        session_id = request.GET.get('session_id')
        if not session_id:
            return JsonResponse({'error': 'Session ID required'}, status=400)
        
        try:
            session = ChatSession.objects.get(session_id=session_id)
            # Получаем последние сообщения
            messages = session.messages.all().order_by('-timestamp')[:10]
            
            messages_data = []
            for msg in messages:
                messages_data.append({
                    'id': str(msg.id),
                    'type': msg.message_type,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'model_used': msg.model_used
                })
            
            return JsonResponse({
                'session_id': session_id,
                'messages': messages_data,
                'is_admin_controlled': session.is_admin_controlled
            })
            
        except ChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)
            
    except Exception as e:
        logger.error(f"Get messages API error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)