"""
Скрипт для создания шаблона промпта для генерации статей на основе поиска в интернете
Запуск: python manage.py shell < Assistant/create_template_script.py
Или: python manage.py shell, затем выполнить код вручную
"""
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ALUKINTERLAB.settings')
django.setup()

from Assistant.models import PromptTemplate
from Blog.models import Category
from django.contrib.auth import get_user_model

User = get_user_model()

def create_internet_search_template():
    """Создание красивого шаблона промпта для генерации статей на основе поиска в интернете"""
    
    # Получаем первого суперпользователя или создаем от его имени
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.first()
    except:
        admin_user = None
    
    # Промпт для генерации заголовка (на основе первых 100 слов контента)
    title_prompt = """Создай привлекательный и информативный заголовок статьи на основе следующего текста.

Текст (первые 100 слов статьи):
{content_first_100_words}

Требования к заголовку:
- Длина: 50-70 символов
- Захватывающий и интригующий
- Соответствует теме из текста
- Используй конкретные факты и цифры, если они есть
- Не используй эмодзи и специальные символы
- Начинай с заглавной буквы

Сгенерируй только заголовок, без дополнительных пояснений."""

    # Промпт для генерации основного контента (на основе спарсенных новостей)
    content_prompt = """Ты - опытный журналист и контент-копирайтер. Напиши информативную и интересную статью на основе предоставленных данных.

КАТЕГОРИЯ: {category}
КЛЮЧЕВЫЕ СЛОВА: {keywords}

ИНФОРМАЦИЯ ИЗ ИСТОЧНИКОВ:
Следующий текст был получен из интернета и содержит актуальную информацию по теме:
{parsed_news_content}

Источник: {news_source}
URL источника: {news_url}

ТРЕБОВАНИЯ К СТАТЬЕ:
1. ОБЪЕМ: 800-1300 слов (строго соблюдай)
2. СТРУКТУРА:
   - Вступление (100-150 слов): краткое представление темы, важность проблемы
   - Основная часть (600-1000 слов): детальный разбор с примерами, фактами, анализом
   - Заключение (100-150 слов): выводы, рекомендации, перспективы

3. СТИЛЬ:
   - Профессиональный, но доступный
   - Используй факты из источника, но переработай их своими словами
   - Добавь свою экспертизу и анализ
   - Избегай прямого копирования текста из источника
   - Используй подзаголовки для структуризации (H2, H3)
   - Добавь нумерованные или маркированные списки где уместно

4. СОДЕРЖАНИЕ:
   - Актуальная информация из источника
   - Экспертный анализ и выводы
   - Конкретные примеры и факты
   - Практические рекомендации (если применимо)
   - Объективность и достоверность

5. ФОРМАТ:
   - Используй HTML разметку: <h2> для подзаголовков, <h3> для подподзаголовков, <p> для параграфов, <ul>/<ol> для списков
   - Не используй <h1> (это уже заголовок статьи)
   - Разделяй параграфы пустой строкой
   - Используй <strong> для выделения важных моментов

ВАЖНО: 
- Статья должна быть уникальной и переработанной, не копией источника
- Используй информацию из источника как основу, но добавляй свой анализ
- Сохраняй объективность и профессионализм
- Строго соблюдай объем 800-1300 слов

Начни писать статью сейчас:"""

    # Промпт для генерации изображения (на основе первых 100 слов контента и заголовка)
    image_prompt = """Создай визуально привлекательное изображение для статьи.

ЗАГОЛОВОК СТАТЬИ: {title}

СОДЕРЖАНИЕ СТАТЬИ (первые 100 слов):
{content_first_100_words}

КАТЕГОРИЯ: {category}

ТРЕБОВАНИЯ К ИЗОБРАЖЕНИЮ:
- Профессиональное и качественное
- Соответствует теме статьи
- Привлекательное и запоминающееся
- Подходит для использования в качестве главного изображения статьи
- Стиль: современный, чистый, информативный

Опиши изображение подробно, которое идеально подходит к статье."""

    # Критерии поиска изображения (для режима search_and_parse)
    image_search_criteria = "{category} {keywords} новости события"

    # Промпт для дополнительной секции (FAQ или интересные факты)
    additional_section_prompt = """Создай дополнительную секцию для статьи в формате FAQ (Часто задаваемые вопросы).

ЗАГОЛОВОК СТАТЬИ: {title}
ОСНОВНОЙ ТЕКСТ СТАТЬИ: {content}

КАТЕГОРИЯ: {category}

ТРЕБОВАНИЯ:
- 3-5 вопросов и ответов
- Вопросы должны быть релевантными к теме статьи
- Ответы должны быть краткими (50-100 слов каждый)
- Используй HTML разметку: <div> для блока FAQ, <h3> для вопросов, <p> для ответов
- Вопросы должны дополнять основную статью полезной информацией

Формат:
<div class="faq-section">
<h3>Вопрос 1?</h3>
<p>Ответ 1...</p>

<h3>Вопрос 2?</h3>
<p>Ответ 2...</p>
...
</div>"""

    # Создаем или обновляем шаблон
    template_name = "Генерация статей на основе поиска в интернете"
    
    # Проверяем, существует ли уже такой шаблон
    template, created = PromptTemplate.objects.get_or_create(
        name=template_name,
        defaults={
            'description': 'Шаблон для генерации статей на основе поиска и парсинга новостей из интернета. Использует режим parse_and_generate: парсит 200-300 слов новостей, затем генерирует полную статью (800-1300 слов) на их основе. Заголовок генерируется из первых 100 слов контента.',
            'is_active': True,
            'title_prompt': title_prompt,
            'content_prompt': content_prompt,
            'image_prompt': image_prompt,
            'image_search_criteria': image_search_criteria,
            'additional_section_prompt': additional_section_prompt,
            'content_generation_mode': 'parse_and_generate',  # Парсинг + генерация
            'image_generation_mode': 'search_and_parse',  # Поиск и парсинг изображения
            'generate_title': True,
            'generate_content': True,
            'generate_image': True,
            'generate_additional_section': True,
            'default_tags': 'новости, интернет, актуальное, технологии',
            'created_by': admin_user,
        }
    )
    
    if not created:
        # Обновляем существующий шаблон
        template.description = 'Шаблон для генерации статей на основе поиска и парсинга новостей из интернета. Использует режим parse_and_generate: парсит 200-300 слов новостей, затем генерирует полную статью (800-1300 слов) на их основе. Заголовок генерируется из первых 100 слов контента.'
        template.is_active = True
        template.title_prompt = title_prompt
        template.content_prompt = content_prompt
        template.image_prompt = image_prompt
        template.image_search_criteria = image_search_criteria
        template.additional_section_prompt = additional_section_prompt
        template.content_generation_mode = 'parse_and_generate'
        template.image_generation_mode = 'search_and_parse'
        template.generate_title = True
        template.generate_content = True
        template.generate_image = True
        template.generate_additional_section = True
        template.default_tags = 'новости, интернет, актуальное, технологии'
        template.save()
        print(f"[OK] Шаблон '{template_name}' обновлен (ID: {template.id})")
    else:
        print(f"[OK] Шаблон '{template_name}' создан (ID: {template.id})")
    
    print(f"\n[INFO] Настройки шаблона:")
    print(f"  - Название: {template.name}")
    print(f"  - Режим генерации контента: {template.get_content_generation_mode_display()}")
    print(f"  - Режим генерации изображения: {template.get_image_generation_mode_display()}")
    print(f"  - Генерация заголовка: {'Да' if template.generate_title else 'Нет'}")
    print(f"  - Генерация контента: {'Да' if template.generate_content else 'Нет'}")
    print(f"  - Генерация изображения: {'Да' if template.generate_image else 'Нет'}")
    print(f"  - Генерация дополнительной секции: {'Да' if template.generate_additional_section else 'Нет'}")
    
    # Показываем доступные категории
    categories = Category.objects.all()[:10]
    if categories:
        print(f"\n[INFO] Доступные категории (первые 10):")
        for cat in categories:
            print(f"  - {cat.title} (ID: {cat.id})")
        print(f"\n[INFO] Чтобы установить категорию по умолчанию, отредактируйте шаблон в админ-панели Django")
    
    return template

if __name__ == '__main__':
    # Запуск при выполнении скрипта напрямую
    template = create_internet_search_template()
    print(f"\n[SUCCESS] Шаблон готов к использованию!")
    print(f"[INFO] ID шаблона: {template.id}")
    print(f"[INFO] Для тестирования используйте ID шаблона: {template.id}")

