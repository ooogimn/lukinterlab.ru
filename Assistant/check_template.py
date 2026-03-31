"""
Скрипт для проверки созданного шаблона
"""
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ALUKINTERLAB.settings')
django.setup()

from Assistant.models import PromptTemplate

template = PromptTemplate.objects.get(id=12)

print("=" * 80)
print("ШАБЛОН ПРОМПТА ДЛЯ ГЕНЕРАЦИИ СТАТЕЙ")
print("=" * 80)
print(f"\nID: {template.id}")
print(f"Название: {template.name}")
print(f"Активен: {'Да' if template.is_active else 'Нет'}")
print(f"\nНАСТРОЙКИ ГЕНЕРАЦИИ:")
print(f"  - Генерация заголовка: {'Да' if template.generate_title else 'Нет'}")
print(f"  - Генерация контента: {'Да' if template.generate_content else 'Нет'}")
print(f"  - Генерация изображения: {'Да' if template.generate_image else 'Нет'}")
print(f"  - Генерация доп. секции: {'Да' if template.generate_additional_section else 'Нет'}")
print(f"\nРЕЖИМЫ:")
print(f"  - Режим генерации контента: {template.get_content_generation_mode_display()}")
print(f"  - Режим генерации изображения: {template.get_image_generation_mode_display()}")
print(f"\nПРОМПТЫ:")
print(f"\n1. ПРОМПТ ДЛЯ ЗАГОЛОВКА (первые 200 символов):")
print("-" * 80)
print(template.title_prompt[:200] + "..." if len(template.title_prompt) > 200 else template.title_prompt)
print(f"\n2. ПРОМПТ ДЛЯ КОНТЕНТА (первые 300 символов):")
print("-" * 80)
print(template.content_prompt[:300] + "..." if len(template.content_prompt) > 300 else template.content_prompt)
print(f"\n3. ПРОМПТ ДЛЯ ИЗОБРАЖЕНИЯ (первые 200 символов):")
print("-" * 80)
print(template.image_prompt[:200] + "..." if len(template.image_prompt) > 200 else template.image_prompt)
print(f"\n4. КРИТЕРИЙ ПОИСКА ИЗОБРАЖЕНИЯ: {template.image_search_criteria}")
print(f"\n5. ДОПОЛНИТЕЛЬНАЯ СЕКЦИЯ:")
print("-" * 80)
print(template.additional_section_prompt[:200] + "..." if len(template.additional_section_prompt) > 200 else template.additional_section_prompt)
print("\n" + "=" * 80)
print("ШАБЛОН ГОТОВ К ИСПОЛЬЗОВАНИЮ!")
print("=" * 80)

