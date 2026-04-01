import re
from django.utils.text import slugify
from django.conf import settings


class SEOUtils:
    """Утилиты для SEO оптимизации"""

    @staticmethod
    def plain_text_for_meta(text):
        """
        Убирает HTML и типичный markdown (# заголовки, **жирный**, ссылки) для сниппетов и keywords.
        """
        if not text:
            return ''
        t = str(text)
        t = re.sub(r'<[^>]+>', ' ', t)
        t = re.sub(r'```[\s\S]*?```', ' ', t)
        t = re.sub(r'`[^`]+`', ' ', t)
        # Заголовки Markdown в любом месте (og:description, сниппеты для превью ссылок)
        t = re.sub(r'#{1,6}\s*', '', t)
        t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
        t = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', t)
        t = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', t)
        t = re.sub(r'[_]{2,}', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t
    
    @staticmethod
    def generate_meta_title(text, max_length=60):
        """Генерация meta title"""
        if len(text) <= max_length:
            return text
        
        # Обрезаем до последнего пробела
        words = text.split()
        result = ""
        for word in words:
            if len(result + " " + word) <= max_length:
                result += " " + word if result else word
            else:
                break
        
        return result.strip()
    
    @staticmethod
    def generate_meta_description(text, max_length=160):
        """Генерация meta description: plain text, длина никогда не превышает max_length."""
        if not text:
            return ''
        text = SEOUtils.plain_text_for_meta(text)
        if not text:
            return ''
        if len(text) <= max_length:
            return text

        ellipsis = '…'
        room = max_length - len(ellipsis)
        if room < 1:
            return text[:max_length]

        words = text.split()
        result = ''
        for word in words:
            candidate = f'{result} {word}'.strip() if result else word
            if len(candidate) <= room:
                result = candidate
            else:
                break

        if not result:
            return text[:room] + ellipsis
        return result + ellipsis
    
    @staticmethod
    def extract_keywords(text, max_keywords=10):
        """Извлечение ключевых слов из текста"""
        if not text:
            return []
        # Удаляем HTML и markdown-разметку
        text = re.sub(r'<[^>]+>', '', str(text))
        text = SEOUtils.plain_text_for_meta(text)
        
        # Приводим к нижнему регистру
        text = text.lower()
        
        # Удаляем знаки препинания
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Разбиваем на слова
        words = text.split()
        
        # Удаляем стоп-слова
        stop_words = {
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она',
            'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее',
            'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда',
            'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до',
            'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей',
            'может', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем',
            'была', 'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет',
            'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь',
            'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем',
            'всех', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть', 'после',
            'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много',
            'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда',
            'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'притом', 'будет',
            'очень', 'мы', 'вместо', 'есть', 'два', 'об', 'другой', 'хоть', 'после', 'над', 'больше',
            'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много', 'разве', 'три',
            'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть',
            'том', 'нельзя', 'такой', 'им', 'более', 'всегда', 'притом', 'будет', 'очень', 'мы',
            'вместо', 'есть', 'два', 'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот',
            'через', 'эти', 'нас', 'про', 'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту',
            'моя', 'впрочем', 'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том',
            'нельзя', 'такой', 'им', 'более', 'всегда', 'притом', 'будет', 'очень', 'мы', 'вместо'
        }
        
        # Фильтруем слова
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Подсчитываем частоту
        word_count = {}
        for word in filtered_words:
            word_count[word] = word_count.get(word, 0) + 1
        
        # Сортируем по частоте
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        
        # Возвращаем топ ключевых слов
        return [word for word, count in sorted_words[:max_keywords]]
    
    @staticmethod
    def generate_slug(text):
        """Генерация SEO-friendly slug"""
        return slugify(text, allow_unicode=True)
    
    @staticmethod
    def optimize_image_alt(image_name, context=""):
        """Генерация alt текста для изображений"""
        # Удаляем расширение файла
        name = re.sub(r'\.[^.]+$', '', image_name)
        
        # Заменяем дефисы и подчеркивания на пробелы
        name = re.sub(r'[-_]', ' ', name)
        
        # Приводим к правильному регистру
        name = name.title()
        
        if context:
            return f"{name} - {context}"
        
        return name
    
    @staticmethod
    def generate_breadcrumb_data(current_page, parent_pages=None):
        """Генерация данных для хлебных крошек"""
        breadcrumbs = [
            {
                "name": "Главная",
                "url": "/",
                "position": 1
            }
        ]
        
        if parent_pages:
            for i, page in enumerate(parent_pages, 2):
                breadcrumbs.append({
                    "name": page["name"],
                    "url": page["url"],
                    "position": i
                })
        
        breadcrumbs.append({
            "name": current_page["name"],
            "url": current_page["url"],
            "position": len(breadcrumbs) + 1
        })
        
        return breadcrumbs
    
    @staticmethod
    def validate_seo_data(title, description, keywords):
        """Валидация SEO данных"""
        errors = []
        
        if not title:
            errors.append("Title не может быть пустым")
        elif len(title) > 60:
            errors.append(f"Title слишком длинный ({len(title)} символов, максимум 60)")
        
        if not description:
            errors.append("Description не может быть пустым")
        elif len(description) > 160:
            errors.append(f"Description слишком длинный ({len(description)} символов, максимум 160)")
        
        if keywords and len(keywords.split(',')) > 10:
            errors.append("Слишком много ключевых слов (максимум 10)")
        
        return errors 