from django.core.management.base import BaseCommand
from home.models import Service, ExtraService, StandaloneExtraService


class Command(BaseCommand):
    help = 'Создает начальные услуги и дополнительные услуги'

    def handle(self, *args, **options):
        self.stdout.write('Создание начальных услуг...')
        
        # Удаляем существующие услуги
        Service.objects.all().delete()
        StandaloneExtraService.objects.all().delete()
        
        # Создаем основные услуги
        services_data = [
            {
                'title': 'Сайты под ключ',
                'description': 'Современные веб-сайты с адаптивным дизайном и SEO-оптимизацией',
                'price': 'от 50,000 ₽',
                'order': 1,
                'extra_services': [
                    {'title': 'Адаптивный дизайн', 'description': '', 'price': '', 'order': 1},
                    {'title': 'SEO-оптимизация', 'description': '', 'price': '', 'order': 2},
                    {'title': 'Интеграция с CRM', 'description': '', 'price': '', 'order': 3},
                    {'title': 'Техническая поддержка', 'description': '', 'price': '', 'order': 4},
                ]
            },
            {
                'title': 'Telegram боты',
                'description': 'Автоматизация бизнес-процессов, продаж, поддержки клиентов и интеграции с внешними сервисами.',
                'price': 'от 30,000 ₽',
                'order': 2,
                'extra_services': [
                    {'title': 'Автоответчики', 'description': '', 'price': '', 'order': 1},
                    {'title': 'Платежные системы', 'description': '', 'price': '', 'order': 2},
                    {'title': 'Автопостинг', 'description': '', 'price': '', 'order': 3},
                    {'title': 'Парсинг данных', 'description': '', 'price': '', 'order': 4},
                ]
            },
            {
                'title': 'Мобильные приложения',
                'description': 'Нативные и кроссплатформенные приложения для iOS и Android',
                'price': 'от 150,000 ₽',
                'order': 3,
                'extra_services': [
                    {'title': 'iOS и Android', 'description': '', 'price': '', 'order': 1},
                    {'title': 'Push-уведомления', 'description': '', 'price': '', 'order': 2},
                    {'title': 'Офлайн режим', 'description': '', 'price': '', 'order': 3},
                    {'title': 'Интеграция с API', 'description': '', 'price': '', 'order': 4},
                ]
            },
            {
                'title': 'Интернет-магазины',
                'description': 'Полнофункциональные онлайн-магазины с интеграцией платежей',
                'price': 'от 100,000 ₽',
                'order': 4,
                'extra_services': [
                    {'title': 'Платежные системы', 'description': '', 'price': '', 'order': 1},
                    {'title': 'Управление товарами', 'description': '', 'price': '', 'order': 2},
                    {'title': 'Аналитика продаж', 'description': '', 'price': '', 'order': 3},
                    {'title': 'Telegram-бот', 'description': '', 'price': '', 'order': 4},
                ]
            }
        ]
        
        # Создаем независимые дополнительные услуги
        standalone_extra_services_data = [
            {
                'title': 'Техническая поддержка',
                'description': 'Круглосуточная поддержка и обслуживание ваших проектов',
                'price': 'от 15,000 ₽/мес',
                'order': 1,
            },
            {
                'title': 'SEO-продвижение',
                'description': 'Повышение позиций в поисковых системах и привлечение трафика',
                'price': 'от 25,000 ₽/мес',
                'order': 2,
            },
            {
                'title': 'Обновление и развитие',
                'description': 'Добавление новых функций и улучшение существующих',
                'price': 'от 20,000 ₽',
                'order': 3,
            }
        ]
        
        # Создаем основные услуги
        for service_data in services_data:
            extra_services = service_data.pop('extra_services')
            service = Service.objects.create(**service_data)
            
            # Создаем дополнительные услуги для основной услуги
            for extra_data in extra_services:
                ExtraService.objects.create(service=service, **extra_data)
            
            self.stdout.write(f'Создана услуга: {service.title}')
        
        # Создаем независимые дополнительные услуги
        for extra_data in standalone_extra_services_data:
            StandaloneExtraService.objects.create(**extra_data)
            self.stdout.write(f'Создана независимая доп. услуга: {extra_data["title"]}')
        
        self.stdout.write(
            self.style.SUCCESS('Успешно создано %d услуг, %d дополнительных услуг в составе и %d независимых дополнительных услуг' % 
                             (Service.objects.count(), ExtraService.objects.count(), StandaloneExtraService.objects.count()))
        ) 