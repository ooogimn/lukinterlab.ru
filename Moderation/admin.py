from django.contrib import admin
from .models import (
    ModerationCriteria, ArticleModeration,
    CommentModerationCriteria, CommentModeration,
    SEOAnalysis, ModerationNotification, ModerationStatistics
)


@admin.register(ModerationCriteria)
class ModerationCriteriaAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created']
    list_filter = ['is_active', 'created']
    search_fields = ['name', 'description']
    readonly_fields = ['created', 'updated']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Критерии', {
            'fields': ('criteria',),
            'description': 'JSON формат: {"min_length": 1000, "max_length": 5000, "required_keywords": [], "forbidden_words": [], "tone": "", "structure": ""}'
        }),
        ('Временные метки', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ArticleModeration)
class ArticleModerationAdmin(admin.ModelAdmin):
    list_display = ['post', 'status', 'moderator', 'submitted_at', 'moderated_at']
    list_filter = ['status', 'submitted_at', 'moderated_at']
    search_fields = ['post__title', 'moderator__username', 'moderator_comment']
    readonly_fields = ['submitted_at', 'moderated_at']
    date_hierarchy = 'submitted_at'
    raw_id_fields = ['post', 'moderator']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('post', 'status', 'moderator')
        }),
        ('Критерии', {
            'fields': ('criteria_used', 'check_results')
        }),
        ('Комментарии', {
            'fields': ('moderator_comment',)
        }),
        ('Временные метки', {
            'fields': ('submitted_at', 'moderated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CommentModerationCriteria)
class CommentModerationCriteriaAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created']
    list_filter = ['is_active', 'created']
    search_fields = ['name', 'description']
    readonly_fields = ['created', 'updated']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Критерии', {
            'fields': ('criteria',),
            'description': 'JSON формат: {"forbidden_words": [], "min_length": 5, "max_length": 2000, "spam_patterns": [], "tone_rules": ""}'
        }),
        ('Действия', {
            'fields': ('actions',),
            'description': 'JSON формат: {"delete": true, "correct": true, "reply": true}'
        }),
        ('Временные метки', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CommentModeration)
class CommentModerationAdmin(admin.ModelAdmin):
    list_display = ['get_comment_display', 'comment_type', 'action', 'checked_at', 'moderated_at']
    list_filter = ['action', 'comment_type', 'checked_at']
    search_fields = ['corrected_text', 'auto_reply']
    readonly_fields = ['checked_at', 'moderated_at', 'content_type', 'object_id']
    date_hierarchy = 'checked_at'
    raw_id_fields = ['content_type', 'criteria_used']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('content_type', 'object_id', 'comment_type', 'action', 'criteria_used')
        }),
        ('Результаты', {
            'fields': ('check_results', 'corrected_text', 'auto_reply')
        }),
        ('Временные метки', {
            'fields': ('checked_at', 'moderated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_comment_display(self, obj):
        """Отображение комментария в списке"""
        if obj.comment:
            try:
                content = obj.get_comment_content()[:50] if obj.get_comment_content() else "Нет содержимого"
                return f"{obj.get_comment_author_name()}: {content}..."
            except:
                return f"ID: {obj.object_id}"
        return f"ID: {obj.object_id}"
    get_comment_display.short_description = 'Комментарий'


@admin.register(SEOAnalysis)
class SEOAnalysisAdmin(admin.ModelAdmin):
    list_display = ['post', 'seo_score', 'focus_keyword', 'analyzed_at']
    list_filter = ['seo_score', 'analyzed_at']
    search_fields = ['post__title', 'meta_title', 'focus_keyword']
    readonly_fields = ['analyzed_at', 'updated_at']
    date_hierarchy = 'analyzed_at'
    raw_id_fields = ['post']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('post', 'seo_score', 'focus_keyword')
        }),
        ('Метаданные', {
            'fields': ('meta_title', 'meta_description')
        }),
        ('Детальный анализ', {
            'fields': ('analysis_data',),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('analyzed_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ModerationNotification)
class ModerationNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'notification_type', 'is_read', 'created']
    list_filter = ['notification_type', 'is_read', 'created']
    search_fields = ['title', 'message', 'recipient__username']
    readonly_fields = ['created']
    date_hierarchy = 'created'
    raw_id_fields = ['recipient', 'article_moderation', 'comment_moderation', 'seo_analysis']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('Связи', {
            'fields': ('article_moderation', 'comment_moderation', 'seo_analysis'),
            'classes': ('collapse',)
        }),
        ('Статус', {
            'fields': ('is_read', 'created')
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    @admin.action(description='Отметить как прочитанные')
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    
    @admin.action(description='Отметить как непрочитанные')
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)


@admin.register(ModerationStatistics)
class ModerationStatisticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'articles_approved', 'articles_rejected', 'seo_avg_score', 'avg_moderation_time']
    list_filter = ['date']
    readonly_fields = ['created', 'updated']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Дата', {
            'fields': ('date',)
        }),
        ('Статьи', {
            'fields': ('articles_pending', 'articles_approved', 'articles_rejected', 'articles_needs_revision')
        }),
        ('Комментарии', {
            'fields': ('comments_pending', 'comments_approved', 'comments_deleted', 'comments_corrected')
        }),
        ('SEO', {
            'fields': ('seo_analyzed', 'seo_avg_score', 'seo_high_score', 'seo_low_score')
        }),
        ('Производительность', {
            'fields': ('avg_moderation_time',)
        }),
        ('Временные метки', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
