"""
Команда для настройки GigaChat API ключей
Использование:
    python manage.py setup_gigachat --auth-key YOUR_AUTHORIZATION_KEY
    python manage.py setup_gigachat --interactive  # интерактивный режим
"""
from django.core.management.base import BaseCommand, CommandError
from Assistant.models import AssistantSettings
import getpass


class Command(BaseCommand):
    help = 'Настройка GigaChat API ключей для генерации статей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auth-key',
            type=str,
            help='GigaChat Authorization Key (новый способ)'
        )
        parser.add_argument(
            '--client-id',
            type=str,
            help='GigaChat Client ID (устаревший способ, требует также --client-secret)'
        )
        parser.add_argument(
            '--client-secret',
            type=str,
            help='GigaChat Client Secret (устаревший способ, требует также --client-id)'
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Интерактивный режим (запрос ключей через ввод)'
        )
        parser.add_argument(
            '--scope',
            type=str,
            choices=['GIGACHAT_API_PERS', 'GIGACHAT_API_B2B', 'GIGACHAT_API_CORP'],
            default='GIGACHAT_API_PERS',
            help='Scope для доступа к GigaChat API'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('[SETUP] НАСТРОЙКА GIGACHAT API'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        # Получаем или создаем настройки
        settings, created = AssistantSettings.objects.get_or_create(
            defaults={
                'is_enabled': True,
                'ai_provider': 'gigachat',
                'ai_model': 'GigaChat',
                'gigachat_scope': options['scope'],
                'gigachat_verify_ssl_certs': True,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Созданы настройки AssistantSettings'))
        else:
            self.stdout.write(self.style.WARNING('[INFO] Используются существующие настройки AssistantSettings'))

        # Интерактивный режим
        if options['interactive']:
            self._interactive_setup(settings, options['scope'])
            return

        # Установка через аргументы командной строки
        auth_key = options.get('auth_key')
        client_id = options.get('client_id')
        client_secret = options.get('client_secret')

        if auth_key:
            # Новый способ - Authorization Key
            settings.set_gigachat_authorization_key(auth_key)
            settings.gigachat_scope = options['scope']
            settings.save()
            self.stdout.write(self.style.SUCCESS('[OK] GigaChat Authorization Key успешно установлен!'))
            self.stdout.write(self.style.WARNING('   (ключ зашифрован и сохранен в базе данных)'))
            return

        if client_id and client_secret:
            # Старый способ - Client ID и Secret
            settings.gigachat_client_id = client_id
            settings.set_gigachat_client_secret(client_secret)
            settings.gigachat_scope = options['scope']
            settings.save()
            self.stdout.write(self.style.SUCCESS('[OK] GigaChat Client ID и Secret успешно установлены!'))
            self.stdout.write(self.style.WARNING('   (ключи зашифрованы и сохранены в базе данных)'))
            self.stdout.write(self.style.WARNING('   [WARNING] Используется устаревший способ авторизации. Рекомендуется использовать Authorization Key.'))
            return

        # Если ничего не указано - показываем помощь
        self.stdout.write(self.style.ERROR('[ERROR] Ошибка: Не указаны параметры для настройки.'))
        self.stdout.write('')
        self.stdout.write('Использование:')
        self.stdout.write('  python manage.py setup_gigachat --auth-key YOUR_AUTHORIZATION_KEY')
        self.stdout.write('  python manage.py setup_gigachat --client-id ID --client-secret SECRET')
        self.stdout.write('  python manage.py setup_gigachat --interactive')
        self.stdout.write('')
        self.stdout.write('Для получения GigaChat Authorization Key:')
        self.stdout.write('  1. Зарегистрируйтесь на https://developers.sber.ru/')
        self.stdout.write('  2. Откройте проект GigaChat API в личном кабинете Studio')
        self.stdout.write('  3. В разделе "Настройки API" нажмите "Получить ключ"')
        self.stdout.write('  4. Скопируйте Authorization Key')
        raise CommandError('Не указаны параметры для настройки')

    def _interactive_setup(self, settings, default_scope):
        """Интерактивная настройка GigaChat"""
        self.stdout.write('Выберите способ авторизации:')
        self.stdout.write('  1. Authorization Key (новый способ, рекомендуется)')
        self.stdout.write('  2. Client ID и Client Secret (устаревший способ)')
        
        choice = input('\nВаш выбор (1 или 2): ').strip()

        if choice == '1':
            # Authorization Key
            self.stdout.write('\nВведите GigaChat Authorization Key:')
            self.stdout.write('(ключ будет скрыт при вводе)')
            auth_key = getpass.getpass('Authorization Key: ')
            
            if not auth_key:
                raise CommandError('Authorization Key не может быть пустым')
            
            scope = input(f'\nScope [{default_scope}]: ').strip() or default_scope
            if scope not in ['GIGACHAT_API_PERS', 'GIGACHAT_API_B2B', 'GIGACHAT_API_CORP']:
                scope = default_scope
                self.stdout.write(self.style.WARNING(f'Неверный scope, используется {default_scope}'))
            
            settings.set_gigachat_authorization_key(auth_key)
            settings.gigachat_scope = scope
            settings.save()
            
            self.stdout.write(self.style.SUCCESS('\n[OK] GigaChat Authorization Key успешно установлен!'))
            self.stdout.write(self.style.WARNING('   (ключ зашифрован и сохранен в базе данных)'))

        elif choice == '2':
            # Client ID и Secret
            self.stdout.write('\nВведите GigaChat Client ID:')
            client_id = input('Client ID: ').strip()
            
            self.stdout.write('\nВведите GigaChat Client Secret:')
            self.stdout.write('(секрет будет скрыт при вводе)')
            client_secret = getpass.getpass('Client Secret: ')
            
            if not client_id or not client_secret:
                raise CommandError('Client ID и Client Secret не могут быть пустыми')
            
            scope = input(f'\nScope [{default_scope}]: ').strip() or default_scope
            if scope not in ['GIGACHAT_API_PERS', 'GIGACHAT_API_B2B', 'GIGACHAT_API_CORP']:
                scope = default_scope
                self.stdout.write(self.style.WARNING(f'Неверный scope, используется {default_scope}'))
            
            settings.gigachat_client_id = client_id
            settings.set_gigachat_client_secret(client_secret)
            settings.gigachat_scope = scope
            settings.save()
            
            self.stdout.write(self.style.SUCCESS('\n[OK] GigaChat Client ID и Secret успешно установлены!'))
            self.stdout.write(self.style.WARNING('   (ключи зашифрованы и сохранены в базе данных)'))
            self.stdout.write(self.style.WARNING('   [WARNING] Используется устаревший способ авторизации. Рекомендуется использовать Authorization Key.'))
        else:
            raise CommandError('Неверный выбор. Используйте 1 или 2.')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('[OK] Настройка GigaChat завершена успешно!'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        self.stdout.write('Теперь вы можете использовать генерацию статей через GigaChat.')

