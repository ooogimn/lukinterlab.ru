from django.contrib import admin
from home.seo_utils import SEOUtils
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.contrib import messages
from django.utils import timezone
from django import forms
from .models import *
from mptt.admin import DraggableMPTTAdmin
from taggit.forms import TagField
from taggit.models import Tag
from taggit.admin import TagAdmin as TaggitTagAdmin

# Отмените регистрацию администратора тега по умолчанию
admin.site.unregister(Tag)

@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    """    Админ-панель модели категорий    """
    list_display = ('tree_actions', 'indented_title', 'post_count', 'post_photo_cat', 'activ', 'parent', 'chat')
    list_display_links = ('indented_title',)
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['post_photo_cat']
    
    fieldsets = (
        ('Основная информация', {'fields': ('title', 'slug','post_photo_cat', 'parent', 'activ')}),
        ('Описание', {'fields': ('kartinka_cat', 'description')}),
        ('Дополнения', {'fields': ('chat', 'chat_id', 'chat_url', 'description_chat')})
    )
    
    # Метод для отображения превью изображения в админке
    @admin.display(description="Изображение", ordering='content')
    def post_photo_cat(self, Blog: Category):
        if Blog.kartinka_cat:
            return mark_safe(f"<img src='{Blog.kartinka_cat.url}' width=50>")
        return "Без фото"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(post_count=Count('posts'))
        return queryset

    @admin.display(description='Количество статей', ordering='post_count')
    def post_count(self, obj):
        return obj.post_count


class PostAdminForm(forms.ModelForm):
    """Форма с валидацией SEO полей"""
    
    class Meta:
        model = Post
        fields = '__all__'
        widgets = {
            'meta_title': forms.TextInput(attrs={
                'maxlength': 60,
                'placeholder': 'До 60 символов (автогенерируется из заголовка)'
            }),
            'meta_description': forms.Textarea(attrs={
                'maxlength': 160,
                'rows': 3,
                'placeholder': 'До 160 символов (автогенерируется из описания или контента)'
            }),
            'meta_keywords': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Ключевые слова через запятую (автогенерируются из тегов и контента)'
            }),
            'focus_keyword': forms.TextInput(attrs={
                'maxlength': 50,
                'placeholder': 'Главное ключевое слово (автогенерируется из заголовка)'
            }),
        }
    
    def clean_meta_title(self):
        meta_title = self.cleaned_data.get('meta_title', '')
        if meta_title and len(meta_title) > 60:
            raise forms.ValidationError(f'Meta Title слишком длинный ({len(meta_title)} символов, максимум 60)')
        return meta_title
    
    def clean_meta_description(self):
        meta_description = (self.cleaned_data.get('meta_description') or '').strip()
        if not meta_description:
            return ''
        normalized = SEOUtils.generate_meta_description(meta_description, 160)
        if len(normalized) > 160:
            normalized = normalized[:160]
        return normalized


class PostFAQInline(admin.TabularInline):
    """Inline для FAQ в админке Post"""
    model = PostFAQ
    extra = 1
    fields = ('question', 'answer', 'order')
    ordering = ('order',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """    Админ-панель модели Post    """
    
    form = PostAdminForm

    list_display = ['title', 'post_photo', 'category', 'status', 'seo_score', 'fixed', 'author', 'created', 'published_at', 'telegram_posted_at', 'vk_posted_at']
    list_display_links = ['title', 'post_photo', 'category']
    list_filter = ['status', 'category', 'author', 'seo_score']
    search_fields = ['title', 'author', 'meta_title', 'focus_keyword']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ['category']
    date_hierarchy = 'created'
    ordering = ['category', 'created']
    save_on_top = True
    readonly_fields = ['post_photo', 'seo_score', 'published_at', 'vk_wall_post_id']
    list_editable = ['status', 'fixed']
    actions = ['publish_selected', 'unpublish_selected', 'mark_as_fixed', 'mark_as_unfixed']
    
    inlines = [PostFAQInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'category', 'author', 'status', 'fixed', 'published_at'),
            'description': '«Дата публикации» проставляется при переходе черновик → опубликовано (не равна дате создания).',
        }),
        ('Содержание', {
            'fields': ('content', 'video'),
            'classes': ('wide',)
        }),
        ('Медиа', {
            'fields': ('kartinka', 'post_photo', 'og_image'),
            'classes': ('wide',)
        }),
        ('SEO настройки', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords', 'focus_keyword', 'seo_score'),
            'classes': ('collapse',),
            'description': 'SEO поля автогенерируются при сохранении, если не указаны вручную. SEO Score обновляется автоматически.'
        }),
        ('Метаданные', {
            'fields': ('tags',),
            'classes': ('collapse',)
        }),
        ('Социальные сети', {
            'fields': ('telegram_posted_at', 'vk_posted_at', 'vk_wall_post_id', 'description'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description="Изображение", ordering='content')
    def post_photo(self, Blog: Post):
        if Blog.kartinka:
            return mark_safe(f"<img src='{Blog.kartinka.url}' width=100>")
        return "Без фото"

    @admin.action(description="Опубликовать выбранные статьи")
    def publish_selected(self, request, queryset):
        """Публикация через save() — срабатывают автопроверка модерации и сигналы."""
        n_ok = 0
        n_skipped = 0
        for post in queryset.select_related():
            if post.status == 'published':
                continue
            post.status = 'published'
            try:
                post.save()
            except Exception as e:
                self.message_user(request, f'Ошибка для «{post.title}»: {e}', messages.ERROR)
                n_skipped += 1
                continue
            post.refresh_from_db()
            if post.status == 'published':
                n_ok += 1
            else:
                n_skipped += 1
        if n_ok:
            self.message_user(request, f'Опубликовано (после автопроверки): {n_ok}.', messages.SUCCESS)
        if n_skipped:
            self.message_user(
                request,
                f'Не опубликовано (черновик после критериев или ошибка): {n_skipped}.',
                messages.WARNING,
            )
    publish_selected.short_description = "Опубликовать выбранные статьи"

    @admin.action(description="Перевести в черновик")
    def unpublish_selected(self, request, queryset):
        """Массовое изменение статуса на 'черновик'"""
        updated = queryset.update(status='draft', updated=timezone.now())
        self.message_user(
            request,
            f'Успешно переведено в черновик {updated} статей.',
            messages.SUCCESS
        )
    unpublish_selected.short_description = "Перевести в черновик"

    @admin.action(description="Отметить как выполненные")
    def mark_as_fixed(self, request, queryset):
        """Массовое изменение статуса 'выполнено' на True"""
        updated = queryset.update(fixed=True, updated=timezone.now())
        self.message_user(
            request,
            f'Успешно отмечено как выполненные {updated} статей.',
            messages.SUCCESS
        )
    mark_as_fixed.short_description = "Отметить как выполненные"

    @admin.action(description="Снять отметку 'выполнено'")
    def mark_as_unfixed(self, request, queryset):
        """Массовое изменение статуса 'выполнено' на False"""
        updated = queryset.update(fixed=False, updated=timezone.now())
        self.message_user(
            request,
            f'Успешно снята отметка "выполнено" с {updated} статей.',
            messages.SUCCESS
        )
    mark_as_unfixed.short_description = "Снять отметку 'выполнено'"


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """
    Админ-панель модели комментариев
    """
    list_per_page = 50
    list_display = ('author_comment', 'content', 'active', 'email', 'post', 'created')
    list_filter = ('active', 'created', 'updated', 'post')
    search_fields = ('author_comment', 'email', 'content', 'post')


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    """Админ-панель модели лайков статей"""
    list_display = ('post', 'user', 'ip_address', 'created')
    list_filter = ('created', 'post')
    search_fields = ('post__title', 'user__username', 'ip_address')
    readonly_fields = ('created',)
    date_hierarchy = 'created'


@admin.register(PostFAQ)
class PostFAQAdmin(admin.ModelAdmin):
    """Админ-панель модели FAQ для статей"""
    list_display = ('question', 'post', 'order', 'created')
    list_filter = ('created', 'post')
    search_fields = ('question', 'answer', 'post__title')
    ordering = ('post', 'order', 'created')
    raw_id_fields = ('post',)


@admin.register(Tag)
class TagAdmin(TaggitTagAdmin):
    list_display = ['name', 'slug', 'post_count']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            post_count=Count('taggit_taggeditem_items')
        ).order_by('-post_count', 'name')

    @admin.display(description='Количество статей')
    def post_count(self, obj):
        return obj.post_count



