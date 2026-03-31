import json
import logging
import base64
import requests
from django.conf import settings
from django.db import models
from django.db.models import Q
from typing import List, Dict, Any
import os

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import gigachat
    GIGACHAT_AVAILABLE = True
except ImportError:
    GIGACHAT_AVAILABLE = False

logger = logging.getLogger(__name__)


class AIService:
    """Сервис для работы с AI моделями"""
    
    def __init__(self, assistant_settings=None):
        """
        Инициализация AI сервиса
        
        Args:
            assistant_settings: Объект AssistantSettings с настройками
        """
        self.assistant_settings = assistant_settings or self._get_default_settings()
        self.provider = self.assistant_settings.ai_provider
        self.model = self.assistant_settings.ai_model
        self.max_tokens = self.assistant_settings.max_tokens
        self.temperature = self.assistant_settings.temperature
        
        # GigaChat настройки
        self.gigachat_authorization_key = self.assistant_settings.get_gigachat_authorization_key()
        self.gigachat_scope = self.assistant_settings.get_gigachat_scope()
        # Проверяем настройку из settings.py сначала (приоритет), потом из БД
        from django.conf import settings as django_settings
        if hasattr(django_settings, 'GIGACHAT_VERIFY_SSL'):
            self.gigachat_verify_ssl = bool(django_settings.GIGACHAT_VERIFY_SSL)
        elif hasattr(self.assistant_settings, 'get_gigachat_verify_ssl'):
            self.gigachat_verify_ssl = self.assistant_settings.get_gigachat_verify_ssl()
        else:
            self.gigachat_verify_ssl = self.assistant_settings.gigachat_verify_ssl_certs
        
        # Обратная совместимость (deprecated)
        self.gigachat_client_id = self.assistant_settings.get_gigachat_client_id()
        self.gigachat_client_secret = self.assistant_settings.get_gigachat_client_secret()
        
        # OpenAI настройки (для обратной совместимости)
        self.openai_api_key = self.assistant_settings.get_openai_api_key()
        
        # Кэш для токенов доступа GigaChat
        self._access_token_cache = None
        self._token_expires_at = None
    
    def _get_default_settings(self):
        """Получить настройки по умолчанию"""
        from .models import AssistantSettings
        return AssistantSettings.objects.first() or AssistantSettings()
    
    def generate_response(self, message: str, context: List[Dict] = None, conversation_history: List[Dict] = None, use_system_prompt: bool = True) -> Dict[str, Any]:
        """
        Генерировать ответ на сообщение пользователя
        
        Args:
            message: Сообщение/промпт для AI
            context: Контекст из базы знаний (для чат-бота)
            conversation_history: История сообщений (для чат-бота)
            use_system_prompt: Использовать ли системный промпт чат-бота (False для генерации статей)
        """
        
        try:
            if self.provider == 'gigachat':
                return self._generate_gigachat_response(message, context, conversation_history, use_system_prompt)
            elif self.provider == 'openai':
                return self._generate_openai_response(message, context, conversation_history, use_system_prompt)
            else:
                logger.warning(f"Неизвестный провайдер AI: {self.provider}")
                return self._generate_local_response(message, context)
                
        except Exception as e:
            logger.error(f"AI API error: {str(e)}")
            return self._generate_local_response(message, context)
    
    def _generate_gigachat_response(self, message: str, context: List[Dict] = None, conversation_history: List[Dict] = None, use_system_prompt: bool = True) -> Dict[str, Any]:
        """Генерировать ответ через GigaChat API"""
        
        # Проверяем наличие ключа авторизации (новый способ)
        if not self.gigachat_authorization_key:
            # Fallback на старый способ для обратной совместимости
            if not self.gigachat_client_id or not self.gigachat_client_secret:
                logger.warning("GigaChat credentials not configured")
                logger.error("[ERROR] GigaChat не настроен! Проверьте настройки AssistantSettings.")
                # Для генерации статей НЕ возвращаем fallback ответ, а возвращаем ошибку
                if not use_system_prompt:
                    return {
                        'content': '',
                        'tokens_used': 0,
                        'model': 'error',
                        'error': 'GigaChat credentials not configured'
                    }
                return self._generate_local_response(message, context)
        
        try:
            # Получаем токен доступа
            access_token = self._get_gigachat_access_token()
            if not access_token:
                logger.error("[ERROR] Не удалось получить токен доступа GigaChat")
                # Для генерации статей НЕ возвращаем fallback ответ
                if not use_system_prompt:
                    return {
                        'content': '',
                        'tokens_used': 0,
                        'model': 'error',
                        'error': 'Failed to get access token'
                    }
                return self._generate_local_response(message, context)
            
            # Формируем историю сообщений
            messages = []
            
            # Системный промпт используется только для чат-бота (use_system_prompt=True)
            if use_system_prompt:
                system_prompt = self._build_system_prompt(context)
                messages.append({"role": "system", "content": system_prompt})
            
            if conversation_history:
                messages.extend(conversation_history)
            
            # Для генерации статей промпт из шаблона - это основное сообщение
            messages.append({"role": "user", "content": message})
            
            # Отправляем запрос к GigaChat API
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Используем имя модели как есть (без префикса GigaChat:)
            model_name = self.model
            
            # Определяем, использовать ли потоковую генерацию
            # Для длинных промптов (>1000 символов) используем streaming
            total_message_length = sum(len(str(m.get('content', ''))) for m in messages)
            use_streaming = total_message_length > 1000 or self.max_tokens > 2000
            
            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": use_streaming
            }
            
            # Если используется streaming, обрабатываем потоково
            if use_streaming:
                return self._process_streaming_response(headers, payload)
            
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                verify=self.gigachat_verify_ssl,
                timeout=60  # Увеличиваем таймаут для длинных запросов
            )
            
            if response.status_code == 200:
                data = response.json()
                usage = data.get('usage', {})
                return {
                    'content': data['choices'][0]['message']['content'],
                    'tokens_used': usage.get('total_tokens', 0),
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'model': self.model,
                    'finish_reason': data['choices'][0].get('finish_reason', 'stop'),
                    'usage': usage  # Сохраняем полную информацию об использовании
                }
            else:
                # Улучшенная обработка ошибок
                try:
                    from .error_handling import GigaChatErrorHandler
                    error_info = GigaChatErrorHandler.handle_error(response)
                    
                    if error_info and error_info.get('action') == 'refresh_token':
                        # Пробуем обновить токен и повторить
                        self._access_token_cache = None
                        self._token_expires_at = None
                        return self._generate_gigachat_response(message, context, conversation_history, use_system_prompt)
                    
                    GigaChatErrorHandler.log_error_for_admin(error_info or {})
                except ImportError:
                    pass  # Модуль error_handling может быть не создан
                
                logger.error(f"GigaChat API error: {response.status_code} - {response.text}")
                # Для генерации статей НЕ возвращаем fallback ответ
                if not use_system_prompt:
                    return {
                        'content': '',
                        'tokens_used': 0,
                        'model': 'error',
                        'error': f'GigaChat API error: {response.status_code}'
                    }
                return self._generate_local_response(message, context)
                
        except Exception as e:
            logger.error(f"GigaChat API error: {str(e)}")
            # Для генерации статей НЕ возвращаем fallback ответ
            if not use_system_prompt:
                return {
                    'content': '',
                    'tokens_used': 0,
                    'model': 'error',
                    'error': str(e)
                }
            return self._generate_local_response(message, context)
    
    def _process_streaming_response(self, headers: Dict, payload: Dict) -> Dict[str, Any]:
        """
        Обработать потоковый ответ от GigaChat API
        
        Args:
            headers: Заголовки запроса
            payload: Тело запроса
            
        Returns:
            Dict с содержимым и метаданными
        """
        import json
        
        try:
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                stream=True,  # Важно для streaming
                verify=self.gigachat_verify_ssl,
                timeout=120  # Увеличенный таймаут для streaming
            )
            
            if response.status_code != 200:
                logger.error(f"GigaChat streaming error: {response.status_code} - {response.text}")
                return self._generate_local_response("", None)
            
            content = ""
            finish_reason = "stop"
            usage_data = {}
            
            for line in response.iter_lines():
                if line:
                    try:
                        # Убираем префикс "data: " если есть
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            line_str = line_str[6:]
                        
                        if line_str.strip() == '[DONE]':
                            break
                        
                        data = json.loads(line_str)
                        
                        if 'choices' in data and len(data['choices']) > 0:
                            choice = data['choices'][0]
                            delta = choice.get('delta', {})
                            
                            # Собираем контент по частям
                            if 'content' in delta:
                                content += delta['content']
                            
                            # Сохраняем finish_reason
                            if 'finish_reason' in choice and choice['finish_reason']:
                                finish_reason = choice['finish_reason']
                        
                        # Собираем информацию об использовании токенов
                        if 'usage' in data:
                            usage_data = data['usage']
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Ошибка парсинга streaming ответа: {str(e)}")
                        continue
                    except Exception as e:
                        logger.warning(f"Ошибка обработки streaming: {str(e)}")
                        continue
            
            return {
                'content': content.strip(),
                'tokens_used': usage_data.get('total_tokens', 0),
                'prompt_tokens': usage_data.get('prompt_tokens', 0),
                'completion_tokens': usage_data.get('completion_tokens', 0),
                'model': self.model,
                'finish_reason': finish_reason,
                'usage': usage_data,
                'streaming': True
            }
            
        except Exception as e:
            logger.error(f"Ошибка потоковой генерации: {str(e)}")
            return self._generate_local_response("", None)
    
    def _get_gigachat_access_token(self) -> str:
        """Получить токен доступа GigaChat"""
        import time
        import uuid
        
        # Проверяем кэш токена
        if self._access_token_cache and self._token_expires_at and time.time() < self._token_expires_at:
            return self._access_token_cache
        
        try:
            # Генерируем уникальный идентификатор запроса (обязательно согласно новой документации)
            rq_uid = str(uuid.uuid4())
            
            # Новый способ авторизации через Authorization Key
            if self.gigachat_authorization_key:
                # Убираем "Basic " из начала, если он есть (для совместимости)
                auth_key = self.gigachat_authorization_key.strip()
                if auth_key.startswith('Basic '):
                    auth_key = auth_key[6:]  # Убираем "Basic "
                
                # Проверяем длину ключа (должен быть примерно 72-100 символов для Base64)
                if len(auth_key) > 150:
                    logger.error(f"[ERROR] Authorization Key слишком длинный ({len(auth_key)} символов). Возможно, это зашифрованный ключ. Используйте ключ из settings.py.")
                    raise ValueError("Authorization Key имеет неправильный формат (слишком длинный)")
                
                headers = {
                    'Authorization': f'Basic {auth_key}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                    'RqUID': rq_uid  # Обязательный заголовок согласно новой документации
                }
                
                data = {
                    'scope': self.gigachat_scope
                }
                
                # Логирование для отладки (без самого ключа)
                logger.debug(f"GigaChat token request: URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth, Scope={self.gigachat_scope}, RqUID={rq_uid}, AuthKey length={len(auth_key)}")
                
                response = requests.post(
                    'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                    headers=headers,
                    data=data,
                    verify=self.gigachat_verify_ssl,
                    timeout=10
                )
            else:
                # Старый способ для обратной совместимости
                credentials = f"{self.gigachat_client_id}:{self.gigachat_client_secret}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                
                headers = {
                    'Authorization': f'Basic {encoded_credentials}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                    'RqUID': rq_uid  # Обязательный заголовок согласно новой документации
                }
                
                data = {
                    'scope': self.gigachat_scope
                }
                
                response = requests.post(
                    'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                    headers=headers,
                    data=data,
                    verify=self.gigachat_verify_ssl,
                    timeout=10
                )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                expires_at = token_data.get('expires_at')
                
                # Кэшируем токен
                self._access_token_cache = access_token
                if expires_at:
                    # Автоматическое определение формата: миллисекунды или секунды
                    # Если expires_at > 9999999999 (больше ~200 лет от 1970), то это миллисекунды
                    if expires_at > 9999999999:
                        # expires_at в миллисекундах (13 цифр) - конвертируем в секунды
                        expires_at_seconds = expires_at / 1000.0
                    else:
                        # expires_at в секундах (10 цифр) - используем как есть
                        expires_at_seconds = float(expires_at)
                    
                    # Вычитаем 60 секунд для обновления за минуту до истечения
                    self._token_expires_at = expires_at_seconds - 60
                else:
                    # Fallback на 30 минут если expires_at не указан
                    self._token_expires_at = time.time() + 1800 - 60
                
                return access_token
            else:
                # Детальное логирование ошибок для диагностики
                logger.error(f"GigaChat auth error ({response.status_code}): {response.text[:200] if response.text else 'No response text'}")
                logger.error(f"Request details: URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth, Scope={self.gigachat_scope}, RqUID={rq_uid[:20]}...")
                logger.error(f"Authorization Key length: {len(self.gigachat_authorization_key) if self.gigachat_authorization_key else 0} символов")
                
                # Для 400 ошибки - дополнительная информация
                if response.status_code == 400:
                    logger.error("[400] Bad Request - возможные причины:")
                    logger.error("  1. Неправильный формат Authorization Key")
                    logger.error("  2. Неправильный scope (должен быть: GIGACHAT_API_PERS, GIGACHAT_API_B2B или GIGACHAT_API_CORP)")
                    logger.error("  3. Неправильный формат RqUID (должен быть UUID v4)")
                    logger.error(f"  4. Ответ сервера: {response.text[:500] if response.text else 'Пустой ответ'}")
                    try:
                        error_json = response.json()
                        logger.error(f"  5. Детали ошибки от API: {error_json}")
                    except:
                        pass
                
                return None
                
        except Exception as e:
            logger.error(f"GigaChat auth error: {str(e)}", exc_info=True)
            return None
    
    def _generate_openai_response(self, message: str, context: List[Dict] = None, conversation_history: List[Dict] = None, use_system_prompt: bool = True) -> Dict[str, Any]:
        """Генерировать ответ через OpenAI API (для обратной совместимости)"""
        
        if not self.openai_api_key or not OPENAI_AVAILABLE:
            logger.warning("OpenAI credentials not configured or library not available")
            return self._generate_local_response(message, context)
        
        try:
            openai.api_key = self.openai_api_key
            
            # Формируем историю сообщений
            messages = []
            
            # Системный промпт используется только для чат-бота (use_system_prompt=True)
            if use_system_prompt:
                system_prompt = self._build_system_prompt(context)
                messages.append({"role": "system", "content": system_prompt})
            
            if conversation_history:
                messages.extend(conversation_history)
            
            # Для генерации статей промпт из шаблона - это основное сообщение
            messages.append({"role": "user", "content": message})
            
            # Отправляем запрос к OpenAI
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return {
                'content': response.choices[0].message.content,
                'tokens_used': response.usage.total_tokens,
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return self._generate_local_response(message, context)
    
    def _build_system_prompt(self, context: List[Dict] = None) -> str:
        """Строит системный промпт для AI"""
        
        base_prompt = """Ты - виртуальный ассистент компании LukInterLab - ведущей AI-лаборатории России.
        
        О КОМПАНИИ (всегда упоминай при общении):
        - Название: LukInterLab - ваша AI-лаборатория
        - Сайт: https://lukinterlab.ru
        - Специализация: Интеграция искусственного интеллекта (ИИ/AI), LLM (Large Language Models), создание саморекламирующих сайтов и самопродающих интернет-магазинов
        - Опыт: 12+ лет, 1500+ реализованных проектов, 753+ довольных клиентов
        - Работаем с: GigaChat API, GPT (OpenAI), Gemini (Google), DeepSeek, Grok (xAI) и другими AI-моделями
        
        НАШИ УСЛУГИ (активно предлагай):
        1. Интеграция ИИ и LLM - внедрение GigaChat, GPT, Gemini, DeepSeek, Grok (от 80,000 ₽)
        2. Саморекламирующие сайты с ИИ - сайты, которые сами себя продвигают (от 120,000 ₽)
        3. Самопродающие интернет-магазины - магазины с ИИ-рекомендациями и персонализацией (от 150,000 ₽)
        4. ИИ-маркетинг и автоматизация - таргетинг, генерация контента, оптимизация (от 100,000 ₽)
        5. ИИ-боты и ассистенты - интеллектуальные боты для Telegram, WhatsApp, VK (от 60,000 ₽)
        6. Внедрение ИИ в бизнес-процессы - автоматизация, аналитика, CRM с ИИ (от 200,000 ₽)
        
        КОНТАКТЫ (всегда предлагай при запросе):
        - Телефон: +7-905-856-02-82
        - Email: Ya@LukyanovSY.ru
        - Telegram: @LukInterLab_News
        - VK: vk.com/lukinterlab
        - Ссылка на контакты: https://lukinterlab.ru/#contact
        
        ПОЛЕЗНЫЕ ССЫЛКИ (предлагай когда уместно):
        - Корзина: https://lukinterlab.ru/cart/ (для оформления заказа)
        - Услуги: https://lukinterlab.ru/services/ (каталог всех услуг)
        - Контакты: https://lukinterlab.ru/#contact (форма обратной связи)
        - О нас: https://lukinterlab.ru/#about (информация о компании)
        
        ПРАВИЛА ОБЩЕНИЯ:
        1. Отвечай вежливо, дружелюбно и профессионально
        2. Используй русский язык
        3. ВСЕГДА упоминай, что мы специализируемся на ИИ/AI и LLM
        4. Активно предлагай наши услуги, но не навязчиво
        5. При вопросах о заказе - предлагай добавить услуги в корзину или связаться с нами
        6. При вопросах о контактах - давай полную информацию и ссылку на страницу контактов
        7. При вопросах о ценах - указывай диапазон "от X ₽" и предлагай уточнить детали
        8. Если не знаешь ответа - предлагай связаться напрямую через контакты
        9. Будь кратким, но информативным
        10. В конце диалога всегда предлагай: "Могу помочь с оформлением заказа или ответить на другие вопросы!"
        
        ПРИМЕРЫ ОТВЕТОВ:
        - На вопрос "Что вы делаете?": "LukInterLab - ваша AI-лаборатория! Мы специализируемся на интеграции искусственного интеллекта и LLM (GigaChat, GPT, Gemini, DeepSeek, Grok). Создаем саморекламирующие сайты, самопродающие интернет-магазины и внедряем ИИ в бизнес-процессы. Опыт 12+ лет, 1500+ проектов! Хотите узнать больше о наших услугах? [ссылка на услуги]"
        - На вопрос "Как с вами связаться?": "Свяжитесь с нами любым удобным способом: 📞 +7-905-856-02-82, ✉️ Ya@LukyanovSY.ru, Telegram: @LukInterLab_News. Или заполните форму на странице контактов: [ссылка на контакты]"
        - На вопрос "Хочу заказать": "Отлично! Вы можете добавить услуги в корзину на странице услуг [ссылка], или связаться с нами напрямую для консультации. Мы поможем выбрать оптимальное решение с ИИ для вашего бизнеса!"
        
        ВАЖНО: Всегда позиционируй LukInterLab как ведущую AI-лабораторию и эксперта по интеграции ИИ!"""
        
        if context:
            context_text = "\n\nДополнительная информация:\n"
            for item in context:
                context_text += f"- {item['title']}: {item['content'][:200]}...\n"
            base_prompt += context_text
        
        return base_prompt
    
    def _generate_local_response(self, message: str, context: List[Dict] = None) -> Dict[str, Any]:
        """Генерирует ответ без использования внешних AI API"""
        
        message_lower = message.lower()
        
        # Простые правила для ответов
        responses = {
            'привет': 'Привет! Я виртуальный ассистент LukInterLab. Чем могу помочь?',
            'здравствуйте': 'Здравствуйте! Я готов ответить на ваши вопросы о наших услугах.',
            'услуги': 'Мы предоставляем следующие услуги: веб-разработка, автоматизация бизнес-процессов, IT-консалтинг. Подробнее на нашем сайте lukinterlab.ru',
            'цены': 'Цены на наши услуги зависят от сложности проекта. Для получения точной стоимости свяжитесь с нами через контакты на сайте.',
            'контакты': 'Наши контакты: сайт lukinterlab.ru, email Ya@LukyanovSY.ru',
            'помощь': 'Я могу помочь с информацией об услугах, ценах, контактах. Что именно вас интересует?',
            'спасибо': 'Пожалуйста! Обращайтесь, если возникнут еще вопросы.',
            'пока': 'До свидания! Удачного дня!',
        }
        
        # Ищем подходящий ответ
        for keyword, response in responses.items():
            if keyword in message_lower:
                return {
                    'content': response,
                    'tokens_used': len(response.split()),
                    'model': 'local'
                }
        
        # Если есть контекст, используем его
        if context:
            for item in context:
                if any(word in message_lower for word in item['content'].lower().split()[:10]):
                    return {
                        'content': f"По вашему вопросу: {item['content'][:300]}...",
                        'tokens_used': 50,
                        'model': 'local'
                    }
        
        # Стандартный ответ
        return {
            'content': 'Спасибо за ваш вопрос! Для получения подробной информации рекомендую связаться с нами через контакты на сайте lukinterlab.ru или написать на Ya@LukyanovSY.ru',
            'tokens_used': 30,
            'model': 'local'
        }


class KnowledgeBaseService:
    """Сервис для работы с базой знаний"""
    
    @staticmethod
    def search_knowledge(query: str, limit: int = 5) -> List[Dict]:
        """Поиск в базе знаний"""
        from .models import AssistantKnowledge
        
        # Простой поиск по ключевым словам
        keywords = query.lower().split()
        
        knowledge_items = AssistantKnowledge.objects.filter(
            is_active=True
        ).filter(
            Q(keywords__icontains=query) | 
            Q(title__icontains=query) |
            Q(content__icontains=query)
        ).order_by('-priority')[:limit]
        
        results = []
        for item in knowledge_items:
            results.append({
                'id': item.id,
                'title': item.title,
                'content': item.content,
                'category': item.category,
                'keywords': item.keywords
            })
        
        return results
    
    @staticmethod
    def add_knowledge(title: str, content: str, category: str, keywords: str) -> bool:
        """Добавить новую запись в базу знаний"""
        try:
            from .models import AssistantKnowledge
            
            AssistantKnowledge.objects.create(
                title=title,
                content=content,
                category=category,
                keywords=keywords
            )
            return True
        except Exception as e:
            logger.error(f"Error adding knowledge: {str(e)}")
            return False


class AnalyticsService:
    """Сервис для аналитики чата"""
    
    @staticmethod
    def update_daily_analytics():
        """Обновить ежедневную аналитику"""
        from .models import ChatSession, ChatMessage, ChatAnalytics
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        
        # Получаем данные за сегодня
        sessions = ChatSession.objects.filter(created_at__date=today)
        messages = ChatMessage.objects.filter(session__in=sessions)
        
        # Создаем или обновляем запись аналитики
        analytics, created = ChatAnalytics.objects.get_or_create(
            date=today,
            defaults={
                'total_sessions': sessions.count(),
                'total_messages': messages.count(),
                'unique_users': sessions.values('ip_address').distinct().count(),
                'avg_response_time': messages.filter(message_type='assistant').aggregate(
                    avg_time=models.Avg('response_time')
                )['avg_time'] or 0,
                'satisfaction_rate': messages.filter(is_helpful=True).count() / max(messages.count(), 1) * 100
            }
        )
        
        if not created:
            analytics.total_sessions = sessions.count()
            analytics.total_messages = messages.count()
            analytics.unique_users = sessions.values('ip_address').distinct().count()
            analytics.avg_response_time = messages.filter(message_type='assistant').aggregate(
                avg_time=models.Avg('response_time')
            )['avg_time'] or 0
            analytics.satisfaction_rate = messages.filter(is_helpful=True).count() / max(messages.count(), 1) * 100
            analytics.save()
        
        return analytics


class GigaChatAPIService:
    """Расширенный сервис для работы с GigaChat API"""
    
    def __init__(self, assistant_settings):
        self.assistant_settings = assistant_settings
        self.gigachat_authorization_key = assistant_settings.get_gigachat_authorization_key()
        self.gigachat_scope = assistant_settings.get_gigachat_scope()
        self.gigachat_verify_ssl = assistant_settings.gigachat_verify_ssl_certs
        
        # Кэш для токенов доступа
        self._access_token_cache = None
        self._token_expires_at = None
    
    def _get_access_token(self) -> str:
        """Получить токен доступа"""
        import time
        import uuid
        
        # Проверяем кэш токена
        if self._access_token_cache and self._token_expires_at and time.time() < self._token_expires_at:
            return self._access_token_cache
        
        try:
            # Генерируем уникальный идентификатор запроса
            rq_uid = str(uuid.uuid4())
            
            headers = {
                'Authorization': f'Basic {self.gigachat_authorization_key}',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': rq_uid
            }
            
            data = {
                'scope': self.gigachat_scope
            }
            
            response = requests.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data=data,
                verify=self.gigachat_verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                expires_at = token_data.get('expires_at')
                
                # Кэшируем токен
                self._access_token_cache = access_token
                if expires_at:
                    # Автоматическое определение формата: миллисекунды или секунды
                    # Если expires_at > 9999999999 (больше ~200 лет от 1970), то это миллисекунды
                    if expires_at > 9999999999:
                        # expires_at в миллисекундах (13 цифр) - конвертируем в секунды
                        expires_at_seconds = expires_at / 1000.0
                    else:
                        # expires_at в секундах (10 цифр) - используем как есть
                        expires_at_seconds = float(expires_at)
                    
                    # Вычитаем 60 секунд для обновления за минуту до истечения
                    self._token_expires_at = expires_at_seconds - 60
                else:
                    # Fallback на 30 минут если expires_at не указан
                    self._token_expires_at = time.time() + 1800 - 60
                
                return access_token
            else:
                # Детальное логирование ошибок для диагностики
                error_details = {
                    'status_code': response.status_code,
                    'response_text': response.text[:500] if response.text else 'No response text',
                    'headers_sent': {k: v[:50] if isinstance(v, str) and len(v) > 50 else v for k, v in headers.items() if k != 'Authorization'},
                    'data_sent': data,
                    'url': 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
                }
                logger.error(f"GigaChat auth error ({response.status_code}): {response.text[:200]}")
                logger.error(f"Request details: URL={error_details['url']}, Scope={error_details['data_sent'].get('scope')}, RqUID={rq_uid[:20]}...")
                
                # Для 400 ошибки - дополнительная информация
                if response.status_code == 400:
                    logger.error("[400] Bad Request - проверьте:")
                    logger.error("  1. Правильность Authorization Key (должен быть Base64 строка)")
                    logger.error("  2. Правильность scope (должен быть: GIGACHAT_API_PERS, GIGACHAT_API_B2B или GIGACHAT_API_CORP)")
                    logger.error("  3. Формат заголовков (должен быть RqUID с UUID форматом)")
                
                return None
                
        except Exception as e:
            logger.error(f"GigaChat auth error: {str(e)}", exc_info=True)
            return None
    
    def get_models(self) -> List[Dict]:
        """Получить список доступных моделей"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                return []
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                'https://gigachat.devices.sberbank.ru/api/v1/models',
                headers=headers,
                verify=self.gigachat_verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            else:
                logger.error(f"Error getting models: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting models: {str(e)}")
            return []
    
    def get_balance(self) -> Dict:
        """
        Получить остаток токенов с кэшированием
        
        Возвращает структуру:
        {
            "data": [
                {
                    "model": "GigaChat-2-Lite",
                    "balance": 5000000  # остаток токенов
                },
                ...
            ]
        }
        
        Примечание: API /balance доступен только при использовании пакетов токенов.
        При подписке (subscription) возвращает 403.
        """
        from django.core.cache import cache
        
        cache_key = 'gigachat_balance'
        cached_balance = cache.get(cache_key)
        
        if cached_balance:
            logger.debug("Используется кэшированный баланс GigaChat")
            return cached_balance
        
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.warning("Не удалось получить access token для запроса баланса")
                return {}
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                'https://gigachat.devices.sberbank.ru/api/v1/balance',
                headers=headers,
                verify=self.gigachat_verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                try:
                    balance_data = response.json()
                    
                    # Проверяем структуру ответа
                    if not isinstance(balance_data, dict):
                        logger.error(f"Неожиданный формат ответа API balance: {type(balance_data)}")
                        return {}
                    
                    if 'data' not in balance_data:
                        logger.warning("API balance вернул ответ без поля 'data'")
                        logger.debug(f"Структура ответа: {balance_data}")
                        # Возможно, структура другая - пробуем использовать весь ответ
                        balance_data = {'data': [balance_data]} if balance_data else {'data': []}
                    
                    # Валидация структуры данных
                    if isinstance(balance_data.get('data'), list):
                        for item in balance_data['data']:
                            if not isinstance(item, dict):
                                logger.warning(f"Неожиданный формат элемента в data: {type(item)}")
                                continue
                            if 'model' not in item or 'balance' not in item:
                                logger.warning(f"Элемент data не содержит 'model' или 'balance': {item}")
                    
                    # Кэшируем на 5 минут (300 секунд)
                    cache.set(cache_key, balance_data, 300)
                    logger.info(f"Баланс GigaChat получен из API: {len(balance_data.get('data', []))} моделей")
                    logger.debug(f"Детали баланса: {balance_data}")
                    return balance_data
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON ответа balance: {str(e)}")
                    logger.debug(f"Ответ сервера: {response.text[:500]}")
                    return {}
            elif response.status_code == 403:
                # 403 - метод доступен только при покупке пакетов токенов
                # Это нормально для подписок (subscription) - токены не ограничены пакетами
                logger.info("API баланс недоступен (403): используется подписка или pay-as-you-go без пакетов токенов")
                # Не кэшируем 403, чтобы при покупке пакета данные обновились
                return {}
            elif response.status_code == 401:
                logger.error("Ошибка авторизации при запросе баланса (401): токен доступа недействителен")
                return {}
            else:
                logger.error(f"Ошибка получения баланса: {response.status_code} - {response.text[:200]}")
                return {}
                
        except requests.exceptions.Timeout:
            logger.error("Таймаут при запросе баланса GigaChat API")
            return {}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ошибка подключения к GigaChat API: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении баланса: {str(e)}", exc_info=True)
            return {}
    
    def count_tokens(self, text: str, model: str = "GigaChat") -> int:
        """Подсчитать количество токенов в тексте"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                return 0
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                "model": model,
                "input": [text]
            }
            
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/tokens/count',
                headers=headers,
                json=payload,
                verify=self.gigachat_verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0].get('tokens', 0)
            else:
                logger.error(f"Error counting tokens: {response.status_code} - {response.text}")
                return 0
                
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            return 0
    
    def create_embeddings(self, texts: List[str], model: str = "Embeddings") -> List[List[float]]:
        """Создать эмбеддинги для текстов"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                return []
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                "model": model,
                "input": texts
            }
            
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/embeddings',
                headers=headers,
                json=payload,
                verify=self.gigachat_verify_ssl,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                embeddings = []
                for item in data.get('data', []):
                    embeddings.append(item.get('embedding', []))
                return embeddings
            else:
                logger.error(f"Error creating embeddings: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error creating embeddings: {str(e)}")
            return []
