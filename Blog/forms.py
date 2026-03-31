from django import forms
from .models import Comment, Post, Category
from django.core.mail import send_mail
from django.conf import settings
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from taggit.forms import TagField


class EmailPostForm(forms.Form):
    name = forms.CharField(max_length=25)
    email = forms.EmailField()
    to = forms.EmailField()
    comments = forms.CharField(required=False, widget=forms.Textarea)


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('author_comment', 'email', 'content')
        widgets = {
            'author_comment': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors duration-300',
                'placeholder': 'Ваше имя'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors duration-300',
                'placeholder': 'your@email.com'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors duration-300',
                'rows': 4,
                'placeholder': 'Ваш комментарий...'
            })
        }

    def __init__(self, *args, **kwargs):
        self.parent_comment = kwargs.pop('parent_comment', None)
        super().__init__(*args, **kwargs)
        
        if self.parent_comment:
            # Если это ответ на комментарий, изменяем placeholder
            self.fields['content'].widget.attrs['placeholder'] = f'Ответ на комментарий от {self.parent_comment.author_comment}...'
            # Скрываем поля, которые уже заполнены в родительском комментарии
            self.fields['author_comment'].widget.attrs['value'] = self.parent_comment.author_comment
            self.fields['email'].widget.attrs['value'] = self.parent_comment.email
            self.fields['author_comment'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['readonly'] = True


class SearchForm(forms.Form):
    query = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors duration-300',
        'placeholder': 'Поиск по статьям...'
    }))


class PostEditForm(forms.ModelForm):
    """Форма для редактирования статьи"""
    class Meta:
        model = Post
        fields = ['title', 'slug', 'category', 'content', 'video', 'kartinka', 'description', 'status', 'fixed', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Заголовок статьи'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'url-slug'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
            }),
            'content': CKEditorUploadingWidget(attrs={
                'class': 'w-full'
            }),
            'video': CKEditorUploadingWidget(config_name='vstavka', attrs={
                'class': 'w-full'
            }),
            'kartinka': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'rows': 4,
                'placeholder': 'Описание для Telegram'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
            }),
            'fixed': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-primary-600 border-gray-300 rounded focus:ring-primary-500'
            }),
        }
    
    # Используем TagField для тегов
    tags = TagField(required=False, help_text='Введите теги через запятую')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Получаем все категории для выбора
        self.fields['category'].queryset = Category.objects.all()
        # Делаем slug необязательным при редактировании
        if self.instance and self.instance.pk:
            self.fields['slug'].required = False
            # Устанавливаем начальное значение тегов
            if self.instance.pk:
                tags_list = [tag.name for tag in self.instance.tags.all()]
                self.fields['tags'].initial = ', '.join(tags_list)
        
        # Настраиваем виджет для тегов
        self.fields['tags'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Теги через запятую'
        })
    