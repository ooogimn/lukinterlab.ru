from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from home.models import Service, Cart, CartItem, Customer
from decimal import Decimal


class Command(BaseCommand):
    help = 'Тестирование оформления заказа с созданием аккаунта'

    def handle(self, *args, **options):
        # Создаем тестовую услугу, если её нет
        service, created = Service.objects.get_or_create(
            title='Тестовая услуга',
            defaults={
                'description': 'Тестовая услуга для проверки',
                'price': 'от 10,000 ₽',
                'order': 1,
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Создана тестовая услуга: {service.title}')
            )
        
        # Проверяем существующих пользователей
        existing_users = User.objects.filter(username__startswith='test_user')
        self.stdout.write(f'Найдено тестовых пользователей: {existing_users.count()}')
        
        # Создаем тестового пользователя
        username = f'test_user_{existing_users.count() + 1}'
        user = User.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='testpass123',
            first_name='Тест',
            last_name='Пользователь'
        )
        
        # Создаем профиль заказчика
        customer = Customer.objects.create(
            user=user,
            phone='+7 999 999-99-99'
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Создан тестовый пользователь:\n'
                f'Логин: {username}\n'
                f'Пароль: testpass123\n'
                f'Email: {user.email}\n'
                f'ID заказчика: {customer.id}'
            )
        )
        
        # Создаем тестовую корзину
        cart = Cart.objects.create(session_key=f'test_session_{username}')
        
        # Добавляем услугу в корзину
        cart_item = CartItem.objects.create(
            cart=cart,
            service_type='service',
            service_id=service.id,
            title=service.title,
            price=service.price,
            quantity=1
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Создана тестовая корзина:\n'
                f'ID корзины: {cart.id}\n'
                f'Товаров в корзине: {cart.items.count()}\n'
                f'Общая стоимость: {cart.get_total_price()} ₽'
            )
        )
        
        self.stdout.write(
            self.style.WARNING(
                '\nДля тестирования:\n'
                f'1. Перейдите на /cart/\n'
                f'2. Нажмите "Оформить заказ"\n'
                f'3. Заполните форму с данными:\n'
                f'   - Имя: Тест Пользователь\n'
                f'   - Email: {user.email}\n'
                f'   - Телефон: +7 999 999-99-99\n'
                f'   - Логин: {username}_new\n'
                f'   - Пароль: newpass123\n'
                f'4. После оформления заказа вы автоматически войдете в личный кабинет'
            )
        ) 