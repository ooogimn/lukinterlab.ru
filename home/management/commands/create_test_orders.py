from django.core.management.base import BaseCommand
from home.models import Order, OrderItem, Service, StandaloneExtraService
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Создает тестовые заказы для демонстрации системы оплаты'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Количество тестовых заказов для создания'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        # Получаем существующие услуги
        services = Service.objects.filter(is_active=True)
        extra_services = StandaloneExtraService.objects.filter(is_active=True)
        
        if not services.exists() and not extra_services.exists():
            self.stdout.write(
                self.style.ERROR('Нет активных услуг. Сначала создайте услуги.')
            )
            return
        
        # Тестовые данные клиентов
        test_customers = [
            {
                'name': 'Иван Петров',
                'email': 'ivan.petrov@example.com',
                'phone': '+7 (999) 123-45-67'
            },
            {
                'name': 'Мария Сидорова',
                'email': 'maria.sidorova@example.com',
                'phone': '+7 (999) 234-56-78'
            },
            {
                'name': 'Алексей Козлов',
                'email': 'alexey.kozlov@example.com',
                'phone': '+7 (999) 345-67-89'
            },
            {
                'name': 'Елена Волкова',
                'email': 'elena.volkova@example.com',
                'phone': '+7 (999) 456-78-90'
            },
            {
                'name': 'Дмитрий Соколов',
                'email': 'dmitry.sokolov@example.com',
                'phone': '+7 (999) 567-89-01'
            }
        ]
        
        # Статусы заказов для демонстрации
        order_statuses = ['new', 'processing', 'confirmed', 'in_progress', 'completed']
        payment_statuses = ['pending', 'paid', 'failed']
        
        created_orders = []
        
        for i in range(count):
            # Выбираем случайного клиента
            customer = random.choice(test_customers)
            
            # Создаем заказ
            order = Order.objects.create(
                customer_name=customer['name'],
                customer_email=customer['email'],
                customer_phone=customer['phone'],
                total_price=Decimal('0.00'),
                status=random.choice(order_statuses),
                payment_status=random.choice(payment_statuses)
            )
            
            # Добавляем товары в заказ
            total_price = Decimal('0.00')
            
            # Добавляем основную услугу (если есть)
            if services.exists():
                service = random.choice(services)
                price_str = service.price.replace('₽', '').replace(',', '').replace('от', '').replace(' ', '')
                try:
                    price = Decimal(price_str)
                except:
                    price = Decimal('50000.00')
                
                OrderItem.objects.create(
                    order=order,
                    service_type='service',
                    service_id=service.id,
                    title=service.title,
                    price=service.price,
                    quantity=1
                )
                total_price += price
            
            # Добавляем дополнительную услугу (если есть)
            if extra_services.exists() and random.choice([True, False]):
                extra_service = random.choice(extra_services)
                price_str = extra_service.price.replace('₽', '').replace(',', '').replace('от', '').replace(' ', '')
                try:
                    price = Decimal(price_str)
                except:
                    price = Decimal('15000.00')
                
                OrderItem.objects.create(
                    order=order,
                    service_type='extra_service',
                    service_id=extra_service.id,
                    title=extra_service.title,
                    price=extra_service.price,
                    quantity=1
                )
                total_price += price
            
            # Обновляем общую стоимость заказа
            order.total_price = total_price
            order.save()
            
            created_orders.append(order)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Создан заказ №{order.order_number} для {order.customer_name} '
                    f'на сумму {order.total_price} ₽ (статус: {order.get_status_display()}, '
                    f'оплата: {order.get_payment_status_display()})'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Успешно создано {len(created_orders)} тестовых заказов!'
            )
        )
        
        # Показываем статистику
        pending_orders = Order.objects.filter(payment_status='pending').count()
        paid_orders = Order.objects.filter(payment_status='paid').count()
        failed_orders = Order.objects.filter(payment_status='failed').count()
        
        self.stdout.write(f'\n📊 Статистика заказов:')
        self.stdout.write(f'   Ожидают оплаты: {pending_orders}')
        self.stdout.write(f'   Оплачены: {paid_orders}')
        self.stdout.write(f'   Ошибка оплаты: {failed_orders}')
        
        self.stdout.write(
            f'\n🔗 Для просмотра заказов перейдите в админ-панель: '
            f'http://127.0.0.1:8000/admin/home/order/'
        ) 