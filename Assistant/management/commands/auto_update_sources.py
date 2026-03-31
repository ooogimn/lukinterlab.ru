"""
Команда для автоматического обновления конфигурации источников через GigaChat
"""
from django.core.management.base import BaseCommand
from Assistant.news_parser import NewsParserService
from Blog.models import Category


class Command(BaseCommand):
    help = 'Автоматически обновляет конфигурацию источников через GigaChat'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            help='Название источника для обновления (например, VC.ru или IXBT.com)'
        )
        parser.add_argument(
            '--discover',
            action='store_true',
            help='Найти новые источники для категорий блога'
        )
        parser.add_argument(
            '--category-id',
            type=int,
            help='ID категории блога для поиска источников'
        )
        parser.add_argument(
            '--category-title',
            type=str,
            help='Название категории блога для поиска источников'
        )
        parser.add_argument(
            '--all-categories',
            action='store_true',
            help='Найти источники для всех активных категорий блога'
        )

    def handle(self, *args, **options):
        parser_service = NewsParserService()
        
        if options['source']:
            # Обновление конкретного источника
            self.stdout.write(f'Обновление источника: {options["source"]}...')
            success = parser_service.auto_update_source_config(options['source'])
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Источник {options["source"]} успешно обновлен')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'✗ Ошибка обновления источника {options["source"]}')
                )
        
        elif options['discover']:
            # Поиск новых источников
            if options['all_categories']:
                # Поиск для всех активных категорий
                categories = Category.objects.filter(activ=True).order_by('title')
                self.stdout.write(f'Поиск источников для {categories.count()} категорий...')
                
                total_sources = 0
                for category in categories:
                    self.stdout.write(f'\n--- Категория: {category.title} (ID: {category.id}) ---')
                    new_sources = parser_service.auto_discover_news_sources(
                        category_title=category.title,
                        language='ru'
                    )
                    total_sources += len(new_sources)
                    
                    if new_sources:
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Найдено {len(new_sources)} источников:')
                        )
                        for source in new_sources:
                            self.stdout.write(f'  - {source["name"]}: {source["base_url"]}')
                            self.stdout.write(f'    Категория: {source.get("category_title", "N/A")}')
                    else:
                        self.stdout.write(self.style.WARNING('  Источники не найдены'))
                
                self.stdout.write(
                    self.style.SUCCESS(f'\n✓ Всего найдено {total_sources} новых источников')
                )
            
            elif options['category_id']:
                # Поиск для конкретной категории по ID
                try:
                    category = Category.objects.get(pk=options['category_id'], activ=True)
                    self.stdout.write(f'Поиск источников для категории: {category.title}...')
                    
                    new_sources = parser_service.auto_discover_news_sources(
                        category_id=category.id,
                        language='ru'
                    )
                    
                    if new_sources:
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Найдено {len(new_sources)} источников:')
                        )
                        for source in new_sources:
                            self.stdout.write(f'  - {source["name"]}: {source["base_url"]}')
                            self.stdout.write(f'    Селекторы:')
                            self.stdout.write(f'      article_selector: {source["article_selector"]}')
                            self.stdout.write(f'      title_selector: {source["title_selector"]}')
                    else:
                        self.stdout.write(self.style.WARNING('Источники не найдены'))
                except Category.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'Категория с ID {options["category_id"]} не найдена')
                    )
            
            elif options['category_title']:
                # Поиск для конкретной категории по названию
                try:
                    category = Category.objects.get(title=options['category_title'], activ=True)
                    self.stdout.write(f'Поиск источников для категории: {category.title}...')
                    
                    new_sources = parser_service.auto_discover_news_sources(
                        category_title=category.title,
                        language='ru'
                    )
                    
                    if new_sources:
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Найдено {len(new_sources)} источников:')
                        )
                        for source in new_sources:
                            self.stdout.write(f'  - {source["name"]}: {source["base_url"]}')
                    else:
                        self.stdout.write(self.style.WARNING('Источники не найдены'))
                except Category.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'Категория "{options["category_title"]}" не найдена')
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        'Укажите категорию: --category-id, --category-title или --all-categories'
                    )
                )
        
        else:
            self.stdout.write(
                self.style.ERROR(
                    'Укажите действие: --source для обновления источника или --discover для поиска новых'
                )
            )

