"""
Management command для создания тестовых промпт-шаблонов
"""
from django.core.management.base import BaseCommand
from Assistant.models import PromptTemplate
from Blog.models import Category
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Создание тестовых промпт-шаблонов для разных сценариев'

    def handle(self, *args, **options):
        self.stdout.write('Создание тестовых промпт-шаблонов...')
        
        # Получаем или создаем категорию по умолчанию
        default_category, _ = Category.objects.get_or_create(
            slug='vysoko-intellektualnye-novosti',
            defaults={
                'title': 'Высоко интеллектуальные новости',
                'description': 'Категория по умолчанию'
            }
        )
        
        # Получаем суперюзера для created_by
        superuser = User.objects.filter(is_superuser=True).first()
        
        templates_data = [
            {
                'name': 'Полная генерация - все элементы',
                'description': 'Шаблон с полной генерацией всех элементов: заголовок, текст, изображение, дополнительная секция FAQ',
                'is_active': True,
                'title_prompt': """Создай привлекательный заголовок для статьи на тему {topic} в категории {category}.
Заголовок должен быть интересным, содержать эмодзи и привлекать внимание читателей.
Используй ключевые слова: {keywords}
Стиль: современный, технологичный, инновационный.""",
                'content_prompt': """Напиши уникальную статью на тему {topic} в категории {category}.

ВАЖНО: LukInterLab - это передовая компания в области искусственного интеллекта и IT-технологий. 
Мы идём в ногу со временем и даже быстрее, используя все новейшие технологии и AI.

Требования:
- Объем: 800-1300 слов (строго соблюдать)
- Тон: экспертный, инновационный, вдохновляющий
- Структура: введение, основная часть с подзаголовками (h2, h3), практические примеры, заключение
- HTML разметка: h2, h3, ul, ol, blockquote, strong, p
- Подчеркни возможности ИИ и IT технологий
- Добавь информацию о том, как LukInterLab может помочь в реализации подобных проектов
- Используй ключевые слова: {keywords}
- Избегай копирования, пиши уникальный контент
- Начни с заголовка: {title}""",
                'image_prompt': """Создай стильное изображение для статьи "{title}" на тему {topic}. 
Изображение должно быть привлекательным, профессиональным и соответствовать теме статьи.
Стиль: современный, технологичный, связанный с искусственным интеллектом и IT.""",
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': True,
                'generate_content': True,
                'generate_image': True,
                'generate_additional_section': True,
                'additional_section_prompt': """На основе основной статьи создай HTML-блок FAQ.

Найди в основном тексте ситуации, персонажей, действия, цифры, предметы. Каждый вопрос обязан ссылаться на такой элемент.

Сформулируй 5–7 вопросов, начинающихся с «Как», «Почему», «Что», «Когда», «Можно ли», «Стоит ли», «Сколько», «Какие». В вопросе всегда должно быть упоминание конкретной детали из основной статьи {content}.

В ответе обязательно перефразируй или процитируй факт из {content}. 

Никаких выдуманных подробностей — только информация из {content}. Можно чуть расширить мысль, если остаёшься в рамках здравого смысла и явно опираешься на исходный текст.

Строго соблюдай структуру HTML-блока:

<section class="faq-section">
<h2>❓ Частые вопросы</h2>
<div class="faq-item">
<h3>Вопрос 1: ...?</h3>
<p>Ответ...</p>
</div>
...
</section>

Запрещено: Markdown, обратные кавычки, пояснения, комментарии вне HTML. Любые теги кроме <section>, <h2>, <div>, <h3>, <p>.""",
                'default_category': default_category,
                'default_tags': 'AI, технологии, инновации, IT'
            },
            {
                'name': 'Частичная генерация - текст + изображение',
                'description': 'Генерация только текста и изображения, без дополнительной секции',
                'is_active': True,
                'title_prompt': """Создай заголовок для статьи на тему {topic}.
Заголовок должен быть информативным и привлекательным.""",
                'content_prompt': """Напиши статью на тему {topic} в категории {category}.

Требования:
- Объем: 800-1300 слов
- Структура: введение, основная часть, заключение
- HTML разметка: h2, h3, p, ul, ol
- Используй ключевые слова: {keywords}
- Начни с заголовка: {title}""",
                'image_prompt': """Создай изображение для статьи "{title}" на тему {topic}.
Стиль: современный, профессиональный.""",
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': True,
                'generate_content': True,
                'generate_image': True,
                'generate_additional_section': False,
                'additional_section_prompt': '',
                'default_category': default_category,
                'default_tags': 'новости, технологии'
            },
            {
                'name': 'Только заголовок',
                'description': 'Генерация только заголовка статьи',
                'is_active': True,
                'title_prompt': """Создай креативный и привлекательный заголовок для статьи на тему {topic} в категории {category}.
Заголовок должен быть цепляющим, содержать эмодзи и использовать ключевые слова: {keywords}""",
                'content_prompt': '',
                'image_prompt': '',
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': True,
                'generate_content': False,
                'generate_image': False,
                'generate_additional_section': False,
                'additional_section_prompt': '',
                'default_category': default_category,
                'default_tags': ''
            },
            {
                'name': 'Только изображение',
                'description': 'Генерация только изображения для статьи',
                'is_active': True,
                'title_prompt': '',
                'content_prompt': '',
                'image_prompt': """Создай стильное и привлекательное изображение для статьи на тему {topic}.
Изображение должно быть профессиональным, современным и соответствовать теме.
Стиль: технологичный, инновационный.""",
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': False,
                'generate_content': False,
                'generate_image': True,
                'generate_additional_section': False,
                'additional_section_prompt': '',
                'default_category': default_category,
                'default_tags': ''
            },
            {
                'name': 'Только текст',
                'description': 'Генерация только основного текста статьи',
                'is_active': True,
                'title_prompt': '',
                'content_prompt': """Напиши подробную статью на тему {topic} в категории {category}.

Требования:
- Объем: 800-1300 слов
- Структура: введение, основная часть с подзаголовками (h2, h3), заключение
- HTML разметка: h2, h3, p, ul, ol, blockquote, strong
- Используй ключевые слова: {keywords}
- Тон: экспертный, информативный""",
                'image_prompt': '',
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': False,
                'generate_content': True,
                'generate_image': False,
                'generate_additional_section': False,
                'additional_section_prompt': '',
                'default_category': default_category,
                'default_tags': 'статья, контент'
            },
            {
                'name': 'Текст + FAQ блок',
                'description': 'Генерация текста с дополнительной секцией FAQ',
                'is_active': True,
                'title_prompt': """Создай заголовок для статьи на тему {topic}.""",
                'content_prompt': """Напиши статью на тему {topic} в категории {category}.

Требования:
- Объем: 800-1300 слов
- Структура: введение, основная часть, заключение
- HTML разметка: h2, h3, p
- Используй ключевые слова: {keywords}
- Начни с заголовка: {title}""",
                'image_prompt': '',
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': True,
                'generate_content': True,
                'generate_image': False,
                'generate_additional_section': True,
                'additional_section_prompt': """На основе статьи "{title}" и контента {content} создай HTML-блок FAQ.

Сгенерируй 5-7 вопросов и ответов, которые могут возникнуть у читателей после прочтения статьи.

Структура:
<section class="faq-section">
<h2>❓ Часто задаваемые вопросы</h2>
<div class="faq-item">
<h3>Вопрос 1: ...?</h3>
<p>Ответ...</p>
</div>
...
</section>

Только HTML, без Markdown и комментариев.""",
                'default_category': default_category,
                'default_tags': 'FAQ, вопросы'
            },
            {
                'name': 'Только FAQ блок',
                'description': 'Генерация только дополнительной секции FAQ (для создания отдельного FAQ блока)',
                'is_active': True,
                'title_prompt': '',
                'content_prompt': '',
                'image_prompt': '',
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': False,
                'generate_content': False,
                'generate_image': False,
                'generate_additional_section': True,
                'additional_section_prompt': """Создай универсальный HTML-блок FAQ на основе темы {topic} и ключевых слов {keywords}.

Сгенерируй 5-7 вопросов и ответов, которые могут быть интересны читателям.

Структура:
<section class="faq-section">
<h2>❓ Часто задаваемые вопросы</h2>
<div class="faq-item">
<h3>Вопрос 1: ...?</h3>
<p>Ответ...</p>
</div>
...
</section>

Только HTML, без Markdown.""",
                'default_category': default_category,
                'default_tags': 'FAQ'
            },
            {
                'name': 'Парсинг + генерация',
                'description': 'Поиск и парсинг 200 слов из интернета + генерация текста на их основе',
                'is_active': True,
                'title_prompt': """Создай заголовок для статьи на основе темы {topic}.""",
                'content_prompt': """На основе следующих данных из интернета: {parsed_news_content}

Напиши уникальную статью на тему {topic}.

Требования:
- Объем: 800-1300 слов
- Используй информацию из парсинга как основу, но пиши свой уникальный текст
- Структура: введение, основная часть, заключение
- HTML разметка: h2, h3, p
- Используй ключевые слова: {keywords}
- Начни с заголовка: {title}""",
                'image_prompt': """Создай изображение для статьи "{title}".""",
                'content_generation_mode': 'parse_and_generate',
                'image_generation_mode': 'generate',
                'generate_title': True,
                'generate_content': True,
                'generate_image': True,
                'generate_additional_section': False,
                'additional_section_prompt': '',
                'default_category': default_category,
                'default_tags': 'парсинг, новости'
            },
            {
                'name': 'Полный парсинг',
                'description': 'Полный парсинг статьи из указанных источников',
                'is_active': True,
                'title_prompt': '',
                'content_prompt': 'https://example.com/article1\nhttps://example.com/article2',
                'image_prompt': '',
                'content_generation_mode': 'full_parse',
                'image_generation_mode': 'search_and_parse',
                'image_search_criteria': 'новости, технологии',
                'generate_title': False,
                'generate_content': True,
                'generate_image': True,
                'generate_additional_section': False,
                'additional_section_prompt': '',
                'default_category': default_category,
                'default_tags': 'парсинг'
            },
            {
                'name': 'Мотивационные слоганы',
                'description': 'Генерация текста с дополнительной секцией мотивационных слоганов',
                'is_active': True,
                'title_prompt': """Создай мотивационный заголовок для статьи на тему {topic}.""",
                'content_prompt': """Напиши вдохновляющую статью на тему {topic}.

Требования:
- Объем: 800-1300 слов
- Тон: мотивационный, вдохновляющий, позитивный
- Структура: введение, основная часть, заключение
- HTML разметка: h2, h3, p
- Используй ключевые слова: {keywords}
- Начни с заголовка: {title}""",
                'image_prompt': '',
                'content_generation_mode': 'generate',
                'image_generation_mode': 'generate',
                'generate_title': True,
                'generate_content': True,
                'generate_image': False,
                'generate_additional_section': True,
                'additional_section_prompt': """На основе статьи "{title}" и контента {content} создай HTML-блок с 3 мотивационными слоганами.

Слоганы должны быть:
- Вдохновляющими
- Краткими (1-2 предложения)
- Связанными с темой статьи

Структура:
<section class="motivational-section">
<h2>💪 Мотивационные слоганы</h2>
<div class="slogan-item">
<p><strong>Слоган 1:</strong> ...</p>
</div>
<div class="slogan-item">
<p><strong>Слоган 2:</strong> ...</p>
</div>
<div class="slogan-item">
<p><strong>Слоган 3:</strong> ...</p>
</div>
</section>

Только HTML, без Markdown.""",
                'default_category': default_category,
                'default_tags': 'мотивация, вдохновение'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for template_data in templates_data:
            try:
                template, created = PromptTemplate.objects.update_or_create(
                    name=template_data['name'],
                    defaults={
                        **template_data,
                        'created_by': superuser
                    }
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'[ERROR] Ошибка при создании шаблона {template_data["name"]}: {str(e)}'))
                continue
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'[OK] Создан шаблон: {template.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'[UPDATE] Обновлен шаблон: {template.name}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] Готово! Создано: {created_count}, Обновлено: {updated_count}'
        ))

