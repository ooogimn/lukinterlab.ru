"""
Формы для управления автопостингом
"""
from datetime import datetime, time as dt_time, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import PromptTemplate, AISchedule, NewsSearchSettings
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
            'default_category', 'default_tags', 'news_search_suffix',
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
            'news_search_suffix': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр.: последние события, обзор (к поиску новостей)',
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
            'news_search_suffix': 'Уточнение поиска новостей',
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


# Виджеты дашборда расписаний: заметные границы и фокус (Tailwind CDN в base.html)
_SCHEDULE_CONTROL = (
    'schedule-dash-control w-full rounded-lg border-2 border-slate-300 bg-white px-3 py-2 '
    'text-sm text-slate-900 shadow-sm transition placeholder:text-slate-400 '
    'hover:border-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 '
    'focus:ring-indigo-200'
)
_SCHEDULE_TEXTAREA = (
    _SCHEDULE_CONTROL
    + ' min-h-[4.5rem] resize-y leading-snug text-[13px] bg-slate-50/80'
)
_SCHEDULE_CHECK = 'schedule-dash-check h-5 w-5 rounded border-2 border-slate-400 text-indigo-600 focus:ring-indigo-500'


class NewsSearchSettingsForm(forms.ModelForm):
    """Настройки пула поиска новостей (дашборд «Поиск новостей»)."""

    class Meta:
        model = NewsSearchSettings
        fields = [
            'ddg_query_suffix',
            'ddg_search_url_template',
            'search_per_source_limit',
            'search_max_collect',
            'search_pool_timeout',
            'search_parallel_max',
            'freshness_hours',
            'penalize_unknown_published',
            'rank_random_jitter',
            'query_variant_suffixes',
            'force_fresh_news_on_content_retry',
            'top_list_random_offset_max',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ctrl = _SCHEDULE_CONTROL
        ta = _SCHEDULE_TEXTAREA
        self.fields['ddg_query_suffix'].widget = forms.TextInput(attrs={'class': ctrl})
        self.fields['ddg_search_url_template'].widget = forms.TextInput(attrs={'class': ctrl})
        for name in (
            'search_per_source_limit',
            'search_max_collect',
            'search_pool_timeout',
            'search_parallel_max',
            'freshness_hours',
            'top_list_random_offset_max',
        ):
            self.fields[name].widget = forms.NumberInput(attrs={'class': ctrl, 'min': 0})
        self.fields['query_variant_suffixes'].widget = forms.Textarea(attrs={'class': ta, 'rows': 2})
        for name in ('penalize_unknown_published', 'rank_random_jitter', 'force_fresh_news_on_content_retry'):
            self.fields[name].widget = forms.CheckboxInput(attrs={'class': _SCHEDULE_CHECK})

    def clean_ddg_search_url_template(self):
        v = (self.cleaned_data.get('ddg_search_url_template') or '').strip()
        if '{query}' not in v:
            raise ValidationError('В URL должен быть плейсхолдер {query}.')
        return v


def _first_run_hour_choices():
    """Часы 0–23 в привычном 24-часовом виде (без AM/PM)."""
    cho = []
    for h in range(24):
        if h == 0:
            label = '00:00 — полночь'
        elif h == 12:
            label = '12:00 — полдень'
        else:
            label = f'{h:02d}:00'
        cho.append((h, label))
    return cho


class AIScheduleForm(forms.ModelForm):
    """Форма для создания/редактирования расписания"""

    first_run_date = forms.DateField(
        label='Дата',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': _SCHEDULE_CONTROL,
        }),
    )
    first_run_hour = forms.TypedChoiceField(
        label='Час (24 ч)',
        coerce=int,
        choices=_first_run_hour_choices(),
        widget=forms.Select(attrs={'class': _SCHEDULE_CONTROL}),
    )
    first_run_minute = forms.IntegerField(
        label='Минуты',
        min_value=0,
        max_value=59,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': _SCHEDULE_CONTROL,
            'min': 0,
            'max': 59,
        }),
    )
    
    class Meta:
        model = AISchedule
        fields = [
            'name', 'prompt_template', 'is_active',
            'interval_hours', 'interval_minutes',
            'max_schedule_runs',
            'articles_per_run', 'batch_interval',
            'category', 'tags', 'keywords',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': _SCHEDULE_CONTROL,
                'placeholder': 'Название расписания',
            }),
            'prompt_template': forms.Select(attrs={
                'class': _SCHEDULE_CONTROL,
            }),
            'interval_hours': forms.NumberInput(attrs={
                'class': _SCHEDULE_CONTROL,
                'min': 0,
                'max': 8760,
                'id': 'id_interval_hours',
            }),
            'interval_minutes': forms.NumberInput(attrs={
                'class': _SCHEDULE_CONTROL,
                'min': 0,
                'max': 59,
                'id': 'id_interval_minutes',
            }),
            'max_schedule_runs': forms.NumberInput(attrs={
                'class': _SCHEDULE_CONTROL,
                'min': 1,
                'id': 'id_max_schedule_runs',
            }),
            'articles_per_run': forms.NumberInput(attrs={
                'class': _SCHEDULE_CONTROL,
                'min': 1,
                'max': 10,
            }),
            'batch_interval': forms.NumberInput(attrs={
                'class': _SCHEDULE_CONTROL,
                'min': 0,
                'max': 1440,
                'id': 'id_batch_interval',
            }),
            'category': forms.Select(attrs={
                'class': _SCHEDULE_CONTROL,
            }),
            'tags': forms.TextInput(attrs={
                'class': _SCHEDULE_CONTROL,
                'placeholder': 'Теги через запятую',
            }),
            'keywords': forms.Textarea(attrs={
                'class': _SCHEDULE_TEXTAREA,
                'rows': 3,
                'placeholder': 'Ключевые слова через запятую',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': _SCHEDULE_CHECK,
            }),
        }
        labels = {
            'name': 'Название расписания',
            'prompt_template': 'Шаблон промпта',
            'is_active': 'Активно',
            'interval_hours': 'Интервал между запусками — часы',
            'interval_minutes': 'Интервал — минуты',
            'max_schedule_runs': 'Всего запусков (пусто = бесконечно)',
            'articles_per_run': 'Статей за раз',
            'batch_interval': 'Интервал между статьями в пачке (мин)',
            'category': 'Категория',
            'tags': 'Теги',
            'keywords': 'Ключевые слова',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['prompt_template'].queryset = PromptTemplate.objects.filter(is_active=True)
        self.fields['category'].queryset = Category.objects.all()
        self.fields['max_schedule_runs'].required = False
        self.fields['max_schedule_runs'].help_text = 'Оставьте пустым для неограниченного числа циклов.'
        if self.instance.pk and self.instance.first_run_at:
            lt = timezone.localtime(self.instance.first_run_at)
            self.initial.setdefault('first_run_date', lt.date())
            self.initial.setdefault('first_run_hour', lt.hour)
            self.initial.setdefault('first_run_minute', lt.minute)
        elif not self.instance.pk:
            t = (timezone.now() + timedelta(hours=1)).replace(second=0, microsecond=0)
            lt = timezone.localtime(t)
            self.initial.setdefault('first_run_date', lt.date())
            self.initial.setdefault('first_run_hour', lt.hour)
            self.initial.setdefault('first_run_minute', lt.minute)
            self.initial.setdefault('interval_hours', 24)
            self.initial.setdefault('interval_minutes', 0)
    
    def clean(self):
        cleaned = super().clean()
        h = cleaned.get('interval_hours') or 0
        m = cleaned.get('interval_minutes') or 0
        if h * 3600 + m * 60 < 60:
            raise forms.ValidationError(
                'Интервал между запусками должен быть не меньше 1 минуты (сумма часов и минут).'
            )
        return cleaned
    
    def save(self, commit=True):
        obj = super().save(commit=False)
        d = self.cleaned_data['first_run_date']
        hour = self.cleaned_data['first_run_hour']
        minute = self.cleaned_data['first_run_minute']
        naive = datetime.combine(d, dt_time(hour, minute))
        obj.first_run_at = timezone.make_aware(naive, timezone.get_current_timezone())
        sched_fields = (
            'first_run_date', 'first_run_hour', 'first_run_minute',
            'interval_hours', 'interval_minutes', 'is_active',
        )
        sched_changed = any(f in self.changed_data for f in sched_fields)
        if obj.is_active and obj.first_run_at and (not obj.pk or sched_changed):
            obj.sync_next_run()
        if commit:
            obj.save()
        return obj

