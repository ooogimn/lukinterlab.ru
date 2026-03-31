from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse
from home.models import Cart, CartItem, Service, StandaloneExtraService


class Command(BaseCommand):
    help = 'Тестирование формы оформления заказа'

    def handle(self, *args, **options):
        self.stdout.write('Начинаем тестирование формы оформления заказа...')
        
        # Создаем тестовые данные
        client = Client()
        
        # Создаем тестовую услугу, если её нет
        service, created = Service.objects.get_or_create(
            title='Тестовая услуга',
            defaults={
                'description': 'Описание тестовой услуги',
                'price': '1000 ₽',
                'is_active': True,
                'order': 1
            }
        )
        
        if created:
            self.stdout.write(f'Создана тестовая услуга: {service.name}')
        
        # Создаем корзину и добавляем товар
        session = client.session
        session['cart_id'] = 'test-cart-123'
        session.save()
        
        # Создаем корзину
        cart, created = Cart.objects.get_or_create(
            session_id='test-cart-123',
            defaults={'total_price': 0}
        )
        
        if created:
            self.stdout.write(f'Создана тестовая корзина: {cart.id}')
        
        # Добавляем товар в корзину
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            service_type='service',
            service_id=service.id,
            defaults={
                'title': service.name,
                'price': service.price,
                'quantity': 1
            }
        )
        
        if created:
            self.stdout.write(f'Добавлен товар в корзину: {cart_item.title}')
        
        # Тестируем GET запрос к странице оформления заказа
        self.stdout.write('Тестируем GET запрос к странице оформления заказа...')
        response = client.get(reverse('home:checkout'))
        
        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS('✓ GET запрос успешен'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ GET запрос неуспешен: {response.status_code}'))
        
        # Тестируем POST запрос с валидными данными
        self.stdout.write('Тестируем POST запрос с валидными данными...')
        post_data = {
            'customer_name': 'Тест Тестов',
            'customer_email': 'test@example.com',
            'customer_phone': '+7 (999) 123-45-67',
            'create_account': 'on',
            'username': 'testuser',
            'password1': 'testpass123',
            'password2': 'testpass123',
        }
        
        response = client.post(reverse('home:checkout'), post_data)
        
        if response.status_code == 302:  # Редирект
            self.stdout.write(self.style.SUCCESS('✓ POST запрос успешен, получен редирект'))
            self.stdout.write(f'Редирект на: {response.url}')
        else:
            self.stdout.write(self.style.ERROR(f'✗ POST запрос неуспешен: {response.status_code}'))
            if hasattr(response, 'content'):
                self.stdout.write(f'Содержимое ответа: {response.content.decode()[:500]}...')
        
        # Очищаем тестовые данные
        cart.delete()
        self.stdout.write('Тестовые данные очищены')
        
        self.stdout.write(self.style.SUCCESS('Тестирование завершено!')) 