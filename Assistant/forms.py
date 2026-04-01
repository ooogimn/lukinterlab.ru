"""
Формы для управления автопостингом
"""
from django import forms
from .models import PromptTemplate, AISchedule
from Blog.models import Category


class PromptTemplateForm(forms.ModelForm):
    """Форма для создания/редактирования шаблона промпта"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поля промптов необязательными в форме
        # Валидация будет через clean()
        self.fields['title_prompt'].required = False
        self.fields['content_prompt'].required = False
        self.fields['additional_section_prompt'].required = False
    
    class Meta:
        model = PromptTemplate
        fields = [
            'name', 'description', 'is_active',
            'title_prompt', 'content_prompt', 'image_prompt',  # description_prompt удалено
            'default_category', 'default_tags',
            'content_generation_mode', 'image_generation_mode', 'image_search_criteria',
            'generate_title', 'generate_content', 'generate_image',
            'generate_additional_section', 'additional_section_prompt'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название шаблона'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание шаблона'
            }),
            'title_prompt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Промпт для генерации заголовка. Используйте {topic}, {category}, {keywords}'
            }),
            # description_prompt удалено - описание генерируется автоматически из первых 200 слов контента
            'content_prompt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Промпт для генерации основного контента. Используйте {topic}, {category}, {keywords}, {title}'
            }),
            # description_prompt удалено - описание генерируется автоматически из первых 200 слов контента
            'image_prompt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Промпт для генерации изображения (GigaChat-Pro). Используйте {title}, {topic}'
            }),
            'default_category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'default_tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Теги через запятую'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'content_generation_mode': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_content_generation_mode'
            }),
            'image_generation_mode': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_image_generation_mode'
            }),
            'image_search_criteria': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Критерии для поиска изображения (например: "красота, мода, стиль")',
                'id': 'id_image_search_criteria'
            }),
            'additional_section_prompt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Промпт для генерации дополнительного блока. Используйте {title}, {content}, {category}, {keywords}',
                'id': 'id_additional_section_prompt'
            }),
        }
        labels = {
            'name': 'Название шаблона',
            'description': 'Описание',
            'is_active': 'Активен',
            'title_prompt': 'Промпт для заголовка',
            # description_prompt удалено - описание генерируется автоматически
            'content_prompt': 'Промпт для основного контента',
            'image_prompt': 'Промпт для генерации изображения',
            'default_category': 'Категория по умолчанию',
            'default_tags': 'Теги по умолчанию',
            'content_generation_mode': 'Режим генерации контента',
            'image_generation_mode': 'Режим генерации изображения',
            'image_search_criteria': 'Критерий поиска изображения',
            'generate_title': 'Генерировать заголовок',
            'generate_content': 'Генерировать основной текст',
            'generate_image': 'Генерировать изображение',
            'generate_additional_section': 'Генерировать дополнительную секцию',
            'additional_section_prompt': 'Промпт для дополнительной секции',
        }
        help_texts = {
            'title_prompt': 'Используйте переменные: {topic}, {category}, {keywords}',
            # description_prompt удалено - описание генерируется автоматически из первых 200 слов контента
            'content_prompt': 'Используйте переменные: {topic}, {category}, {keywords}, {title}. Первые 200 слов автоматически станут описанием для Telegram.',
            'image_prompt': 'Используйте переменные: {title}, {topic}',
        }
    
    def clean(self):
        """Кастомная валидация формы"""
        cleaned_data = super().clean()
        
        # Проверяем, что если generate_title=True, то title_prompt обязателен
        generate_title = cleaned_data.get('generate_title', False)
        title_prompt = cleaned_data.get('title_prompt', '').strip()
        
        if generate_title and not title_prompt:
            self.add_error('title_prompt', 'Промпт для заголовка обязателен, если включена генерация заголовка')
        elif not generate_title and not title_prompt:
            # Если генерация заголовка выключена, устанавливаем пустое значение
            cleaned_data['title_prompt'] = ''
        
        # Проверяем, что если generate_content=True, то content_prompt обязателен
        generate_content = cleaned_data.get('generate_content', False)
        content_prompt = cleaned_data.get('content_prompt', '').strip()
        
        if generate_content and not content_prompt:
            self.add_error('content_prompt', 'Промпт для контента обязателен, если включена генерация контента')
        elif not generate_content and not content_prompt:
            # Если генерация контента выключена, устанавливаем пустое значение
            cleaned_data['content_prompt'] = ''
        
        # Проверяем, что если generate_additional_section=True, то additional_section_prompt обязателен
        generate_additional_section = cleaned_data.get('generate_additional_section', False)
        additional_section_prompt = cleaned_data.get('additional_section_prompt', '').strip()
        
        if generate_additional_section and not additional_section_prompt:
            self.add_error('additional_section_prompt', 'Промпт для дополнительной секции обязателен, если включена генерация дополнительной секции')
        
        return cleaned_data


class AIScheduleForm(forms.ModelForm):
    """Форма для создания/редактирования расписания"""
    
    class Meta:
        model = AISchedule
        fields = [
            'name', 'prompt_template', 'is_active',
            'frequency', 'cron_expression', 'start_time',
            'articles_per_run', 'batch_interval',
            'category', 'tags', 'keywords', 'context_data',
            'text_model', 'image_model', 'use_image_generation'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название расписания'
            }),
            'prompt_template': forms.Select(attrs={
                'class': 'form-control'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_frequency'
            }),
            'cron_expression': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '0 9 * * *',
                'id': 'id_cron_expression'
            }),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'id': 'id_start_time',
            }),
            'articles_per_run': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
            'batch_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 1440,
                'id': 'id_batch_interval',
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Теги через запятую'
            }),
            'keywords': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ключевые слова через запятую'
            }),
            'context_data': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': '{"topic": "красота", "tone": "дружелюбный"}'
            }),
            'text_model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'GigaChat'
            }),
            'image_model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'GigaChat-Pro'
            }),
            'use_image_generation': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'name': 'Название расписания',
            'prompt_template': 'Шаблон промпта',
            'is_active': 'Активно',
            'frequency': 'Частота генерации',
            'cron_expression': 'CRON выражение',
            'start_time': 'Время старта',
            'articles_per_run': 'Статей за раз',
            'batch_interval': 'Интервал между статьями в пачке (мин)',
            'category': 'Категория',
            'tags': 'Теги',
            'keywords': 'Ключевые слова',
            'context_data': 'Дополнительные данные (JSON)',
            'text_model': 'Модель для текста',
            'image_model': 'Модель для изображений',
            'use_image_generation': 'Генерировать изображения',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Фильтруем только активные шаблоны
        self.fields['prompt_template'].queryset = PromptTemplate.objects.filter(is_active=True)
        self.fields['category'].queryset = Category.objects.all()
    
    def clean_context_data(self):
        """Валидация JSON в context_data"""
        context_data = self.cleaned_data.get('context_data')
        if context_data:
            try:
                import json
                if isinstance(context_data, str):
                    json.loads(context_data)
                return context_data
            except json.JSONDecodeError:
                raise forms.ValidationError('Некорректный JSON формат')
        return context_data
    
    def clean_cron_expression(self):
        """Валидация CRON выражения"""
        frequency = self.cleaned_data.get('frequency')
        cron_expression = self.cleaned_data.get('cron_expression')
        
        if frequency == 'custom' and not cron_expression:
            raise forms.ValidationError('Укажите CRON выражение для произвольного расписания')
        
        if cron_expression and frequency != 'custom':
            # Очищаем CRON, если не используется custom
            return ''
        
        return cron_expression

