from django import forms
from .models import (
    ModerationCriteria, CommentModerationCriteria,
    ArticleModeration, CommentModeration, SEOAnalysis
)


class ModerationCriteriaForm(forms.ModelForm):
    """Форма для критериев модерации статей"""
    
    class Meta:
        model = ModerationCriteria
        fields = ['name', 'description', 'criteria', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'criteria': forms.Textarea(attrs={'rows': 10, 'class': 'json-field'}),
        }


class CommentModerationCriteriaForm(forms.ModelForm):
    """Форма для критериев модерации комментариев"""
    
    # Поля для удобного заполнения вместо JSON
    forbidden_words = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Введите запрещенные слова через запятую: спам, реклама, оскорбление'
        }),
        help_text='Запрещенные слова через запятую'
    )
    
    spam_patterns = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Паттерны спама через запятую: купить, ссылка, http://'
        }),
        help_text='Паттерны спама через запятую'
    )
    
    min_length = forms.IntegerField(
        required=False,
        initial=5,
        min_value=1,
        help_text='Минимальная длина комментария'
    )
    
    max_length = forms.IntegerField(
        required=False,
        initial=2000,
        min_value=1,
        help_text='Максимальная длина комментария'
    )
    
    tone_rules = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text='Правила тона (например: вежливый, без оскорблений)'
    )
    
    # Действия
    action_delete = forms.BooleanField(
        required=False,
        initial=True,
        label='Удалять при нарушении',
        help_text='Автоматически скрывать комментарии с нарушениями'
    )
    
    action_correct = forms.BooleanField(
        required=False,
        initial=False,
        label='Исправлять текст',
        help_text='Автоматически исправлять текст комментария'
    )
    
    action_reply = forms.BooleanField(
        required=False,
        initial=False,
        label='Добавлять ответ',
        help_text='Автоматически добавлять ответ модератора'
    )
    
    class Meta:
        model = CommentModerationCriteria
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                'placeholder': 'Название набора критериев',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                'placeholder': 'Описание критериев'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Делаем поле name обязательным
        self.fields['name'].required = True
        
        # Если редактируем существующий критерий, заполняем поля из JSON
        if self.instance and self.instance.pk:
            criteria_data = self.instance.criteria if isinstance(self.instance.criteria, dict) else {}
            actions_data = self.instance.actions if isinstance(self.instance.actions, dict) else {}
            
            # Заполняем поля из JSON
            if 'forbidden_words' in criteria_data:
                self.fields['forbidden_words'].initial = ', '.join(criteria_data.get('forbidden_words', []))
            if 'spam_patterns' in criteria_data:
                self.fields['spam_patterns'].initial = ', '.join(criteria_data.get('spam_patterns', []))
            if 'min_length' in criteria_data:
                self.fields['min_length'].initial = criteria_data.get('min_length')
            if 'max_length' in criteria_data:
                self.fields['max_length'].initial = criteria_data.get('max_length')
            if 'tone_rules' in criteria_data:
                self.fields['tone_rules'].initial = criteria_data.get('tone_rules', '')
            
            # Заполняем действия
            self.fields['action_delete'].initial = actions_data.get('delete', False)
            self.fields['action_correct'].initial = actions_data.get('correct', False)
            self.fields['action_reply'].initial = actions_data.get('reply', False)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Формируем JSON для criteria (всегда создаем словарь, даже если пустой)
        criteria = {}
        
        if cleaned_data.get('forbidden_words'):
            words = [w.strip() for w in cleaned_data['forbidden_words'].split(',') if w.strip()]
            if words:
                criteria['forbidden_words'] = words
        
        if cleaned_data.get('spam_patterns'):
            patterns = [p.strip() for p in cleaned_data['spam_patterns'].split(',') if p.strip()]
            if patterns:
                criteria['spam_patterns'] = patterns
        
        if cleaned_data.get('min_length'):
            criteria['min_length'] = cleaned_data['min_length']
        
        if cleaned_data.get('max_length'):
            criteria['max_length'] = cleaned_data['max_length']
        
        if cleaned_data.get('tone_rules'):
            criteria['tone_rules'] = cleaned_data['tone_rules']
        
        # Формируем JSON для actions (всегда создаем словарь)
        actions = {
            'delete': cleaned_data.get('action_delete', False),
            'correct': cleaned_data.get('action_correct', False),
            'reply': cleaned_data.get('action_reply', False),
        }
        
        # Сохраняем в cleaned_data для использования в save()
        cleaned_data['_criteria'] = criteria
        cleaned_data['_actions'] = actions
        
        return cleaned_data
    
    def save(self, commit=True):
        """Переопределяем save для правильного сохранения JSON полей"""
        instance = super().save(commit=False)
        
        # Устанавливаем criteria и actions из cleaned_data
        if '_criteria' in self.cleaned_data:
            instance.criteria = self.cleaned_data['_criteria']
        else:
            instance.criteria = {}
            
        if '_actions' in self.cleaned_data:
            instance.actions = self.cleaned_data['_actions']
        else:
            instance.actions = {
                'delete': False,
                'correct': False,
                'reply': False,
            }
        
        if commit:
            instance.save()
        return instance


class ArticleModerationForm(forms.ModelForm):
    """Форма для модерации статьи"""
    
    class Meta:
        model = ArticleModeration
        fields = ['status', 'moderator_comment']
        widgets = {
            'moderator_comment': forms.Textarea(attrs={'rows': 5}),
        }


class CommentModerationForm(forms.ModelForm):
    """Форма для модерации комментария"""
    
    class Meta:
        model = CommentModeration
        fields = ['action', 'corrected_text', 'auto_reply']
        widgets = {
            'corrected_text': forms.Textarea(attrs={'rows': 5}),
            'auto_reply': forms.Textarea(attrs={'rows': 3}),
        }


class SEOAnalysisForm(forms.ModelForm):
    """Форма для SEO анализа"""
    
    class Meta:
        model = SEOAnalysis
        fields = ['meta_title', 'meta_description', 'focus_keyword']
        widgets = {
            'meta_title': forms.TextInput(attrs={'maxlength': 60}),
            'meta_description': forms.Textarea(attrs={'rows': 3, 'maxlength': 160}),
        }

