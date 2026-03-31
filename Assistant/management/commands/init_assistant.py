from django.core.management.base import BaseCommand
from Assistant.models import AssistantSettings, AssistantKnowledge


class Command(BaseCommand):
    help = 'Инициализация AI-ассистента с базовыми настройками и знаниями'

    def handle(self, *args, **options):
        # Создаем настройки ассистента
        settings, created = AssistantSettings.objects.get_or_create(
            defaults={
                'is_enabled': True,
                'welcome_message': 'Привет! Я виртуальный ассистент LukInterLab. Чем могу помочь?',
                'ai_provider': 'gigachat',
                'ai_model': 'GigaChat',
                'max_tokens': 1000,
                'temperature': 0.7,
                'gigachat_scope': 'GIGACHAT_API_PERS',
                'gigachat_verify_ssl_certs': True,
                'auto_start': False,
                'auto_start_delay': 3,
                'assistant_name': 'Сергей',
                'welcome_message_template': 'Доброго дня! Чем можем быть полезны? Я Ассистент {name}, готов ответить на Ваши вопросы. Сейчас действует скидка 30% на сайты с интеграцией AI. Интересно?',
                'use_personalized_greeting': True,
                'show_typing_indicator': True,
                'enable_voice': False,
                'enable_telegram_notifications': False,
                'enable_admin_takeover': False,
                'theme_color': '#667eea',
                'position': 'bottom-right',
                'max_messages_per_session': 50,
                'session_timeout': 30,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Настройки ассистента созданы')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Настройки ассистента уже существуют')
            )

        # Создаем базовые знания
        knowledge_data = [
            {
                'title': 'О компании LukInterLab',
                'category': 'company',
                'content': 'LukInterLab - это IT-компания, специализирующаяся на веб-разработке, автоматизации бизнес-процессов и IT-консалтинге. Мы помогаем бизнесу внедрять современные технологические решения.',
                'keywords': 'компания, о нас, LukInterLab, IT, веб-разработка, автоматизация'
            },
            {
                'title': 'Наши услуги',
                'category': 'services',
                'content': 'Мы предоставляем следующие услуги: разработка веб-сайтов и веб-приложений, автоматизация бизнес-процессов, IT-консалтинг, техническая поддержка, интеграция систем.',
                'keywords': 'услуги, веб-разработка, автоматизация, консалтинг, поддержка'
            },
            {
                'title': 'Контакты',
                'category': 'contacts',
                'content': 'Связаться с нами можно по email: Ya@LukyanovSY.ru или через сайт lukinterlab.ru. Мы всегда готовы обсудить ваш проект и предложить оптимальное решение.',
                'keywords': 'контакты, email, связь, Ya@LukyanovSY.ru, lukinterlab.ru'
            },
            {
                'title': 'Ценообразование',
                'category': 'pricing',
                'content': 'Стоимость наших услуг зависит от сложности проекта, объема работ и сроков выполнения. Для получения точной стоимости рекомендуем связаться с нами для обсуждения деталей проекта.',
                'keywords': 'цены, стоимость, прайс, расчет, проект'
            },
            {
                'title': 'Техническая поддержка',
                'category': 'technical',
                'content': 'Мы предоставляем техническую поддержку для всех наших проектов. Время ответа на запросы - в течение рабочего дня. Для срочных вопросов рекомендуем связаться по телефону.',
                'keywords': 'поддержка, помощь, техническая, срочно, вопрос'
            }
        ]

        created_count = 0
        for item in knowledge_data:
            knowledge, created = AssistantKnowledge.objects.get_or_create(
                title=item['title'],
                defaults={
                    'category': item['category'],
                    'content': item['content'],
                    'keywords': item['keywords'],
                    'priority': 1,
                    'is_active': True
                }
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Создано {created_count} записей в базе знаний')
        )

        self.stdout.write(
            self.style.SUCCESS('Инициализация ассистента завершена успешно!')
        )
        
        self.stdout.write(
            self.style.WARNING('ВАЖНО: Для полной настройки ассистента:')
        )
        self.stdout.write('1. GigaChat API (опционально):')
        self.stdout.write('   - Зарегистрироваться на https://developers.sber.ru/')
        self.stdout.write('   - Открыть проект GigaChat API в личном кабинете Studio')
        self.stdout.write('   - В разделе "Настройки API" нажать "Получить ключ"')
        self.stdout.write('   - Скопировать Authorization Key и настроить в админ-панели')
        self.stdout.write('')
        self.stdout.write('2. Telegram уведомления (опционально):')
        self.stdout.write('   - Создать бота через @BotFather в Telegram')
        self.stdout.write('   - Получить токен бота')
        self.stdout.write('   - Настроить в админ-панели')
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('Ассистент готов к работе!')
        )
