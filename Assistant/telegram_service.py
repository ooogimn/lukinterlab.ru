import requests
import logging
from typing import Optional, Dict, Any
from .models import AssistantSettings, ChatSession

logger = logging.getLogger(__name__)


class TelegramService:
    """Сервис для работы с Telegram Bot API"""
    
    def __init__(self, settings: AssistantSettings):
        self.settings = settings
        self.bot_token = settings.get_telegram_bot_token()
        self.admin_chat_id = settings.telegram_admin_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def is_configured(self) -> bool:
        """Проверить, настроен ли бот"""
        return bool(self.bot_token and self.admin_chat_id)
    
    def send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> Optional[Dict]:
        """Отправить сообщение в Telegram"""
        if not self.is_configured():
            logger.warning("Telegram bot не настроен")
            return None
        
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        if reply_markup:
            data['reply_markup'] = reply_markup
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Telegram send error: {str(e)}")
            return None
    
    def send_notification(self, session: ChatSession, message: str, username: str = None) -> Optional[Dict]:
        """Отправить уведомление администратору о новом сообщении"""
        if not self.settings.enable_telegram_notifications:
            return None
        
        # Формируем сообщение
        user_info = username if username else f"IP: {session.ip_address}"
        text = f"🔔 <b>Новое сообщение от пользователя</b>\n\n"
        text += f"👤 <b>Пользователь:</b> {user_info}\n"
        text += f"📱 <b>Сообщение:</b> {message}\n"
        text += f"🌐 <b>Страница:</b> {session.page_url or 'Неизвестно'}\n"
        text += f"📅 <b>Время:</b> {session.updated_at.strftime('%d.%m.%Y %H:%M')}\n"
        text += f"🆔 <b>Сессия:</b> {session.session_id[:8]}..."
        
        # Создаем кнопки для управления диалогом
        reply_markup = None
        if self.settings.enable_admin_takeover:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "👨‍💼 Вступить в диалог",
                            "callback_data": f"takeover_{session.session_id}"
                        },
                        {
                            "text": "🤖 Автоответчик",
                            "callback_data": f"auto_{session.session_id}"
                        }
                    ]
                ]
            }
        
        return self.send_message(self.admin_chat_id, text, reply_markup)
    
    def send_dialog_update(self, session: ChatSession, message: str, is_user: bool = True) -> Optional[Dict]:
        """Отправить обновление диалога в Telegram"""
        if not self.settings.enable_telegram_notifications:
            return None
        
        # Определяем отправителя
        sender = "👤 Пользователь" if is_user else "🤖 Ассистент"
        text = f"💬 <b>Обновление диалога</b>\n\n"
        text += f"🆔 <b>Сессия:</b> {session.session_id[:8]}...\n"
        text += f"{sender}: {message}\n"
        
        return self.send_message(self.admin_chat_id, text)
    
    def send_admin_response(self, session: ChatSession, message: str) -> Optional[Dict]:
        """Отправить ответ администратора пользователю"""
        if not session.is_admin_controlled:
            return None
        
        # Здесь должна быть логика отправки сообщения пользователю
        # Пока что просто логируем
        logger.info(f"Admin response to session {session.session_id}: {message}")
        
        # Обновляем сессию
        session.save()
        
        return {"status": "sent"}
    
    def handle_callback_query(self, callback_data: str, user_id: str) -> Optional[Dict]:
        """Обработать callback от inline кнопок"""
        if not callback_data.startswith(('takeover_', 'auto_')):
            return None
        
        try:
            action, session_id = callback_data.split('_', 1)
            session = ChatSession.objects.get(session_id=session_id)
            
            if action == 'takeover':
                # Перехватываем диалог администратором
                session.is_admin_controlled = True
                session.admin_user_id = user_id
                session.save()
                
                # Отправляем подтверждение
                return self.send_message(
                    self.admin_chat_id,
                    f"✅ <b>Диалог перехвачен!</b>\n\n"
                    f"🆔 Сессия: {session_id[:8]}...\n"
                    f"Теперь вы управляете диалогом напрямую."
                )
            
            elif action == 'auto':
                # Возвращаем управление ассистенту
                session.is_admin_controlled = False
                session.admin_user_id = ''
                session.save()
                
                # Отправляем подтверждение
                return self.send_message(
                    self.admin_chat_id,
                    f"🤖 <b>Управление передано ассистенту</b>\n\n"
                    f"🆔 Сессия: {session_id[:8]}...\n"
                    f"Диалог продолжается в автоматическом режиме."
                )
                
        except ChatSession.DoesNotExist:
            logger.error(f"Session {session_id} not found")
        except Exception as e:
            logger.error(f"Error handling callback: {str(e)}")
        
        return None


class TelegramWebhookHandler:
    """Обработчик webhook'ов от Telegram"""
    
    def __init__(self, settings: AssistantSettings):
        self.settings = settings
        self.telegram_service = TelegramService(settings)
    
    def handle_update(self, update_data: Dict[str, Any]) -> Dict[str, str]:
        """Обработать обновление от Telegram"""
        try:
            if 'callback_query' in update_data:
                return self._handle_callback_query(update_data['callback_query'])
            elif 'message' in update_data:
                return self._handle_message(update_data['message'])
            else:
                return {"status": "ignored"}
        except Exception as e:
            logger.error(f"Error handling telegram update: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _handle_callback_query(self, callback_query: Dict[str, Any]) -> Dict[str, str]:
        """Обработать callback query"""
        callback_data = callback_query.get('data', '')
        user_id = str(callback_query.get('from', {}).get('id', ''))
        
        result = self.telegram_service.handle_callback_query(callback_data, user_id)
        
        if result:
            return {"status": "success"}
        else:
            return {"status": "error"}
    
    def _handle_message(self, message: Dict[str, Any]) -> Dict[str, str]:
        """Обработать сообщение от администратора"""
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '')
        user_id = str(message.get('from', {}).get('id', ''))
        
        # Проверяем, что сообщение от администратора
        if chat_id != self.settings.telegram_admin_chat_id:
            return {"status": "ignored"}
        
        # Ищем активную сессию, которой управляет этот администратор
        try:
            session = ChatSession.objects.filter(
                is_admin_controlled=True,
                admin_user_id=user_id
            ).first()
            
            if session and text:
                # Отправляем ответ пользователю через ассистента
                self._send_admin_response_to_user(session, text)
                
                # Обновляем диалог в Telegram
                self.send_dialog_update(session, f"👨‍💼 Админ: {text}", False)
                
                logger.info(f"Admin response sent to session {session.session_id}: {text}")
                return {"status": "processed"}
            else:
                # Отправляем список активных сессий
                active_sessions = ChatSession.objects.filter(
                    is_admin_controlled=True
                ).order_by('-updated_at')[:5]
                
                if active_sessions:
                    sessions_text = "Активные диалоги под управлением администратора:\n\n"
                    for sess in active_sessions:
                        sessions_text += f"🆔 {sess.session_id[:8]}... - {sess.updated_at.strftime('%H:%M')}\n"
                    
                    self.telegram_service.send_message(chat_id, sessions_text)
                else:
                    self.telegram_service.send_message(
                        chat_id, 
                        "Нет активных диалогов под управлением администратора."
                    )
                
                return {"status": "processed"}
                
        except Exception as e:
            logger.error(f"Error processing admin message: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _send_admin_response_to_user(self, session: ChatSession, message: str):
        """Отправить ответ администратора пользователю через ассистента"""
        from .models import ChatMessage
        
        try:
            # Сохраняем сообщение администратора в базе данных
            admin_message = ChatMessage.objects.create(
                session=session,
                message_type='assistant',
                content=f"[Администратор] {message}",
                model_used='admin'
            )
            
            logger.info(f"Admin message saved to session {session.session_id}")
            
        except Exception as e:
            logger.error(f"Error saving admin message: {str(e)}")
