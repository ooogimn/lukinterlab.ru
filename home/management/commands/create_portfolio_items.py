"""
Команда для создания работ в портфолио с генерацией изображений через GigaChat
"""
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from home.models import Rabota
from Assistant.models import AssistantSettings
from Assistant.ai_service import AIService
import requests
import re
import base64
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Создает 6 ботов и 6 интернет-магазинов в портфолио с генерацией изображений через GigaChat'

    def handle(self, *args, **options):
        self.stdout.write('Создание работ в портфолио...')
        
        # Получаем настройки GigaChat
        assistant_settings = AssistantSettings.objects.first()
        if not assistant_settings:
            self.stdout.write(self.style.ERROR('Ошибка: AssistantSettings не найдены. Настройте GigaChat в админке.'))
            return
        
        ai_service = AIService(assistant_settings)
        
        # Данные для ботов
        bots_data = [
            {
                'name': 'ИИ-бот для поддержки клиентов',
                'body': 'Интеллектуальный Telegram-бот на базе GigaChat для автоматической поддержки клиентов. Бот отвечает на вопросы, помогает с выбором товаров, обрабатывает заказы и предоставляет информацию о компании 24/7. Интеграция с CRM системой для передачи сложных запросов менеджерам.',
                'technologies': 'Python, Django, Telegram Bot API, GigaChat API, PostgreSQL, Redis, Celery',
                'order': 1
            },
            {
                'name': 'Бот-консультант для интернет-магазина',
                'body': 'Умный бот-консультант с интеграцией LLM (GigaChat Pro) для помощи покупателям в выборе товаров. Бот анализирует предпочтения клиента, предлагает персонализированные рекомендации, обрабатывает заказы и отслеживает статус доставки. Автоматическая интеграция с системой управления складом.',
                'technologies': 'Python, Django, Telegram Bot API, GigaChat Pro, PostgreSQL, REST API, Webhooks',
                'order': 2
            },
            {
                'name': 'Бот для автоматизации бизнес-процессов',
                'body': 'Корпоративный бот для автоматизации внутренних бизнес-процессов. Интеграция с календарем, задачами, CRM и системой учета. Бот напоминает о встречах, создает задачи, генерирует отчеты и отвечает на вопросы сотрудников о компании. Работает в Telegram и корпоративном мессенджере.',
                'technologies': 'Python, Django, Telegram Bot API, GigaChat Max, PostgreSQL, REST API, OAuth2',
                'order': 3
            },
            {
                'name': 'ИИ-бот для образовательной платформы',
                'body': 'Образовательный бот с искусственным интеллектом для помощи студентам. Бот объясняет сложные темы, решает задачи, проверяет домашние задания и готовит к экзаменам. Адаптивное обучение с учетом уровня знаний каждого студента. Интеграция с системой управления обучением.',
                'technologies': 'Python, Django, Telegram Bot API, GigaChat Pro, PostgreSQL, ML модели, API интеграции',
                'order': 4
            },
            {
                'name': 'Бот для бронирования и управления',
                'body': 'Умный бот для автоматизации бронирования в ресторанах, отелях и салонах красоты. Бот принимает бронирования, управляет расписанием, отправляет напоминания клиентам и обрабатывает отмены. Интеграция с календарем и системой оплаты. Автоматическая обработка изменений и уведомления.',
                'technologies': 'Python, Django, Telegram Bot API, GigaChat, PostgreSQL, Payment API, Calendar API',
                'order': 5
            },
            {
                'name': 'Бот-ассистент для HR и рекрутинга',
                'body': 'HR-бот для автоматизации процессов найма и управления персоналом. Бот проводит первичное собеседование, отвечает на вопросы кандидатов, проверяет резюме и координирует встречи с рекрутерами. Интеграция с ATS системой и календарем. Автоматическая отправка отказов и приглашений.',
                'technologies': 'Python, Django, Telegram Bot API, GigaChat Pro, PostgreSQL, ATS API, Calendar API',
                'order': 6
            },
        ]
        
        # Данные для интернет-магазинов
        shops_data = [
            {
                'name': 'Интернет-магазин с ИИ-рекомендациями',
                'body': 'Современный интернет-магазин с интеллектуальной системой рекомендаций на базе GigaChat. Персонализированные предложения товаров, умный поиск с пониманием естественного языка, автоматическая обработка заказов и интеграция с системами доставки. ИИ-чатбот для консультаций покупателей.',
                'technologies': 'Python, Django, React, GigaChat API, PostgreSQL, Redis, Celery, Payment API',
                'order': 7
            },
            {
                'name': 'Самопродающий интернет-магазин с ИИ',
                'body': 'Интеллектуальный интернет-магазин с автоматическим продвижением товаров. ИИ анализирует поведение покупателей, оптимизирует цены, генерирует описания товаров и создает рекламные материалы. Автоматическая обработка заказов, управление складом и интеграция с маркетплейсами.',
                'technologies': 'Python, Django, GigaChat Max, PostgreSQL, Redis, ML модели, API интеграции',
                'order': 8
            },
            {
                'name': 'Интернет-магазин одежды с виртуальной примеркой',
                'body': 'Инновационный интернет-магазин одежды с ИИ-функциями виртуальной примерки и стилиста. Покупатели могут виртуально примерить одежду, получить рекомендации стилиста на базе GigaChat, создать образы и автоматически подобрать размеры. Интеграция с системами доставки и возврата.',
                'technologies': 'Python, Django, React, GigaChat Pro, Computer Vision, PostgreSQL, Payment API',
                'order': 9
            },
            {
                'name': 'Интернет-магазин электроники с ИИ-консультантом',
                'body': 'Специализированный интернет-магазин электроники с интеллектуальным консультантом. ИИ помогает выбрать технику по параметрам, сравнивает модели, отвечает на технические вопросы и создает персонализированные подборки. Автоматическая обработка заказов и интеграция с поставщиками.',
                'technologies': 'Python, Django, GigaChat Pro, PostgreSQL, Elasticsearch, Payment API, Inventory API',
                'order': 10
            },
            {
                'name': 'Интернет-магазин продуктов с умной доставкой',
                'body': 'Интернет-магазин продуктов питания с ИИ-оптимизацией доставки и персонализацией. Система анализирует предпочтения покупателей, предлагает рецепты, создает списки покупок и оптимизирует маршруты доставки. Интеграция с поставщиками, системами оплаты и логистикой.',
                'technologies': 'Python, Django, GigaChat, PostgreSQL, Redis, Route Optimization API, Payment API',
                'order': 11
            },
            {
                'name': 'Интернет-магазин с ИИ-маркетингом',
                'body': 'Интернет-магазин с полностью автоматизированным ИИ-маркетингом. Система генерирует рекламные материалы, создает email-рассылки, оптимизирует цены и управляет рекламными кампаниями. ИИ анализирует поведение покупателей и автоматически настраивает таргетинг для максимальной конверсии.',
                'technologies': 'Python, Django, GigaChat Max, PostgreSQL, Redis, Marketing API, Analytics API',
                'order': 12
            },
        ]
        
        # Создаем ботов
        self.stdout.write('\nСоздание ботов...')
        for bot_data in bots_data:
            self._create_rabota(
                name=bot_data['name'],
                category='bot',
                body=bot_data['body'],
                technologies=bot_data['technologies'],
                order=bot_data['order'],
                ai_service=ai_service,
                image_prompt=f"Современный Telegram-бот с интерфейсом чата, показывающий диалог с пользователем. Стиль: современный, технологичный, дружелюбный. Цвета: синий, фиолетовый, белый. Тема: {bot_data['name']}"
            )
        
        # Создаем интернет-магазины
        self.stdout.write('\nСоздание интернет-магазинов...')
        for shop_data in shops_data:
            self._create_rabota(
                name=shop_data['name'],
                category='shop',
                body=shop_data['body'],
                technologies=shop_data['technologies'],
                order=shop_data['order'],
                ai_service=ai_service,
                image_prompt=f"Современный интернет-магазин с красивым дизайном, показывающий каталог товаров и корзину покупок. Стиль: современный, минималистичный, профессиональный. Цвета: синий, зеленый, белый. Тема: {shop_data['name']}"
            )
        
        self.stdout.write(self.style.SUCCESS('\nУспешно создано 12 работ в портфолио!'))
    
    def _create_rabota(self, name, category, body, technologies, order, ai_service, image_prompt):
        """Создает работу в портфолио с генерацией изображения"""
        try:
            self.stdout.write(f'  Создание: {name}...')
            
            # Генерируем изображение через GigaChat
            image_file = self._generate_image(ai_service, image_prompt)
            
            # Создаем работу
            rabota = Rabota.objects.create(
                name=name,
                category=category,
                body=body,
                technologies=technologies,
                status='completed',
                featured=True,
                order=order,
                adres=''  # Без ссылки по требованию
            )
            
            # Сохраняем изображение
            if image_file:
                rabota.image.save(
                    f"portfolio_{category}_{rabota.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                    image_file,
                    save=True
                )
                self.stdout.write(self.style.SUCCESS(f'    ✓ Создано с изображением'))
            else:
                self.stdout.write(self.style.WARNING(f'    ⚠ Создано без изображения (ошибка генерации)'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    ✗ Ошибка: {str(e)}'))
            logger.error(f"Ошибка создания работы {name}: {str(e)}", exc_info=True)
    
    def _generate_image(self, ai_service, prompt):
        """Генерирует изображение через GigaChat API"""
        try:
            # Получаем токен доступа
            access_token = ai_service._get_gigachat_access_token()
            if not access_token:
                logger.error("Не удалось получить токен доступа GigaChat")
                return None
            
            # Формируем запрос для генерации изображения
            image_request = f"Нарисуй изображение по следующему описанию: {prompt}. Изображение должно быть в формате 800x600 пикселей, современное и профессиональное."
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
            
            # Используем модель, которая поддерживает генерацию изображений
            model = 'GigaChat-2-Pro'  # Pro или Max поддерживают генерацию изображений
            
            payload = {
                'model': model,
                'messages': [
                    {
                        'role': 'user',
                        'content': image_request
                    }
                ],
                'function_call': 'auto',  # Автоматический вызов функции text2image
                'temperature': 0.7,
                'max_tokens': 500
            }
            
            # Отправляем запрос
            response = requests.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=payload,
                verify=ai_service.gigachat_verify_ssl,
                timeout=120
            )
            
            if response.status_code != 200:
                logger.error(f"GigaChat API error: {response.status_code} - {response.text[:200]}")
                return None
            
            response_data = response.json()
            content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Извлекаем file_id из ответа
            # Формат: <img src="file_id" fuse="true"/>
            file_id_match = re.search(r'<img\s+src=["\']([^"\']+)["\']', content)
            if not file_id_match:
                logger.error("Не найден file_id в ответе GigaChat")
                return None
            
            file_id = file_id_match.group(1)
            
            # Скачиваем изображение
            download_url = f'https://gigachat.devices.sberbank.ru/api/v1/files/{file_id}/content'
            download_response = requests.get(
                download_url,
                headers=headers,
                verify=ai_service.gigachat_verify_ssl,
                timeout=60
            )
            
            if download_response.status_code == 200:
                # Проверяем формат ответа
                content_type = download_response.headers.get('Content-Type', '')
                
                if 'application/json' in content_type:
                    # JSON с base64
                    try:
                        download_data = download_response.json()
                        if isinstance(download_data, dict) and 'content' in download_data:
                            image_content = base64.b64decode(download_data['content'])
                        else:
                            image_content = download_response.content
                    except (ValueError, KeyError):
                        image_content = download_response.content
                else:
                    # Бинарные данные
                    image_content = download_response.content
                
                # Создаем ContentFile
                image_file = ContentFile(image_content)
                image_file.name = f"gigachat_generated_{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                
                logger.info(f"Изображение успешно сгенерировано: {len(image_content)} байт")
                return image_file
            else:
                logger.error(f"Ошибка скачивания изображения: {download_response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {str(e)}", exc_info=True)
            return None

