from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ChatSession, ChatMessage, AssistantKnowledge, AssistantSettings, ChatAnalytics,
    PromptTemplate, AISchedule, AIGeneratedArticle, TokenUsage, NewsSource, CategoryStats,
    NewsSearchEndpoint,
    NewsSearchSettings,
)
from . import forms as assistant_forms


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id_short', 'user', 'ip_address', 'created_at', 'is_active', 'messages_count']
    list_filter = ['is_active', 'created_at', 'user']
    search_fields = ['session_id', 'ip_address', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    def session_id_short(self, obj):
        return f"{obj.session_id[:8]}..."
    session_id_short.short_description = 'ID сессии'
    
    def messages_count(self, obj):
        return obj.messages.count()
    messages_count.short_description = 'Сообщений'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'session_short', 'message_type', 'content_short', 'tokens_used', 'response_time']
    list_filter = ['message_type', 'timestamp', 'model_used']
    search_fields = ['content', 'session__session_id']
    readonly_fields = ['id', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def session_short(self, obj):
        return f"{obj.session.session_id[:8]}..."
    session_short.short_description = 'Сессия'
    
    def content_short(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_short.short_description = 'Содержание'


@admin.register(AssistantKnowledge)
class AssistantKnowledgeAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'priority', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['title', 'content', 'keywords']
    list_editable = ['priority', 'is_active']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(AssistantSettings)
class AssistantSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Основные настройки', {
            'fields': ('is_enabled', 'welcome_message', 'auto_start', 'auto_start_delay')
        }),
        ('Персонализация', {
            'fields': ('assistant_name', 'welcome_message_template', 'use_personalized_greeting'),
            'description': 'Настройки персонализации ассистента'
        }),
        ('AI провайдер', {
            'fields': ('ai_provider', 'ai_model', 'max_tokens', 'temperature'),
            'description': 'Выберите провайдера AI и настройте модель'
        }),
        ('GigaChat настройки', {
            'fields': ('gigachat_authorization_key', 'gigachat_scope', 'gigachat_verify_ssl_certs'),
            'description': 'Настройки для подключения к GigaChat API. Получите Authorization Key в личном кабинете Studio.'
        }),
        ('GigaChat настройки (устаревшие)', {
            'fields': ('gigachat_client_id', 'gigachat_client_secret'),
            'description': 'Устаревшие поля для обратной совместимости. Рекомендуется использовать Authorization Key.',
            'classes': ('collapse',)
        }),
        ('OpenAI настройки', {
            'fields': ('openai_api_key',),
            'description': 'Настройки для подключения к OpenAI API (для обратной совместимости)'
        }),
        ('Telegram интеграция', {
            'fields': (
                'telegram_channel_autopost_enabled',
                'enable_telegram_notifications',
                'telegram_bot_token',
                'telegram_admin_chat_id',
                'enable_admin_takeover',
            ),
            'description': 'Автопост в канал — анонсы статей; уведомления админу — отдельная опция.',
        }),
        ('Поведение', {
            'fields': ('show_typing_indicator', 'enable_voice')
        }),
        ('Дизайн', {
            'fields': ('theme_color', 'position')
        }),
        ('Ограничения', {
            'fields': ('max_messages_per_session', 'session_timeout')
        }),
        ('Лимиты токенов подписки', {
            'fields': ('subscription_token_limits',),
            'description': 'Лимиты токенов для подписки GigaChat. Формат JSON: {"GigaChat-2-Max": 50000, "GigaChat-2-Pro": 44400, "GigaChat-2-Lite": 50000}. Если пусто, используются значения по умолчанию. Получите актуальные лимиты в личном кабинете GigaChat Studio.'
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        """Кастомизация формы в зависимости от выбранного провайдера"""
        form = super().get_form(request, obj, **kwargs)
        
        # Добавляем подсказки для полей
        if 'gigachat_scope' in form.base_fields:
            form.base_fields['gigachat_scope'].widget.attrs['placeholder'] = 'GIGACHAT_API_PERS'
        
        return form
    
    def has_add_permission(self, request):
        # Разрешаем только одну запись настроек
        return not AssistantSettings.objects.exists()
    
    def save_model(self, request, obj, form, change):
        """Обработка сохранения с шифрованием секретных данных"""
        # Обрабатываем секретные поля
        if 'gigachat_authorization_key' in form.changed_data:
            obj.set_gigachat_authorization_key(form.cleaned_data['gigachat_authorization_key'])
        
        if 'gigachat_client_secret' in form.changed_data:
            obj.set_gigachat_client_secret(form.cleaned_data['gigachat_client_secret'])
        
        if 'openai_api_key' in form.changed_data:
            obj.set_openai_api_key(form.cleaned_data['openai_api_key'])
        
        if 'telegram_bot_token' in form.changed_data:
            obj.set_telegram_bot_token(form.cleaned_data['telegram_bot_token'])
        
        super().save_model(request, obj, form, change)


@admin.register(ChatAnalytics)
class ChatAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_sessions', 'total_messages', 'unique_users', 'avg_response_time', 'satisfaction_rate']
    list_filter = ['date']
    readonly_fields = ['date']
    date_hierarchy = 'date'
    
    def has_add_permission(self, request):
        return False  # Аналитика создается автоматически


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'default_category', 'created_at', 'created_by']
    list_filter = ['is_active', 'created_at', 'default_category']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'is_active', 'created_by')
        }),
        ('Промпты для генерации', {
            'fields': ('title_prompt', 'content_prompt', 'image_prompt'),  # description_prompt удалено
            'description': 'Промпты для генерации каждого элемента статьи. Используйте {topic}, {category}, {keywords}, {title}, {content} для подстановки значений.'
        }),
        ('Настройки по умолчанию', {
            'fields': ('default_category', 'default_tags', 'news_search_suffix'),
            'description': 'news_search_suffix — доп. фраза к запросу поиска для этого шаблона (глобальные параметры — дашборд «Поиск новостей»).',
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # При создании
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AISchedule)
class AIScheduleAdmin(admin.ModelAdmin):
    form = assistant_forms.AIScheduleForm
    list_display = [
        'name', 'prompt_template', 'interval_hours', 'interval_minutes',
        'is_active', 'articles_per_run', 'completed_schedule_runs', 'max_schedule_runs',
        'total_generated', 'last_run', 'next_run',
    ]
    list_filter = ['is_active', 'created_at', 'prompt_template']
    search_fields = ['name', 'keywords', 'tags']
    readonly_fields = [
        'created_at', 'updated_at', 'created_by', 'total_generated', 'last_run',
        'next_run', 'completed_schedule_runs',
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'prompt_template', 'is_active', 'created_by'),
        }),
        ('Расписание', {
            'fields': (
                'first_run_date', 'first_run_hour', 'first_run_minute',
                'interval_hours', 'interval_minutes',
                'max_schedule_runs', 'completed_schedule_runs',
            ),
            'description': 'Дата и время первого запуска (часы 0–23 в списке, без AM/PM). Пустой лимит запусков = бесконечно.',
        }),
        ('Параметры генерации', {
            'fields': ('articles_per_run', 'batch_interval', 'category', 'tags', 'keywords', 'context_data'),
            'description': 'Параметры, которые будут использоваться при генерации статей. Текст — GigaChat, изображение — GigaChat-Pro (без выбора в расписании).'
        }),
        ('Статистика', {
            'fields': ('total_generated', 'last_run', 'next_run'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # При создании
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['run_schedule_now']
    
    def run_schedule_now(self, request, queryset):
        """Запустить генерацию для выбранных расписаний"""
        from .tasks import run_schedule_task
        from django_q.tasks import async_task
        
        for schedule in queryset:
            async_task('Assistant.tasks.run_schedule_task', schedule.id, True)
            self.message_user(request, f"Запущена генерация для расписания: {schedule.name}")
    
    run_schedule_now.short_description = "Запустить генерацию сейчас"


@admin.register(AIGeneratedArticle)
class AIGeneratedArticleAdmin(admin.ModelAdmin):
    list_display = ['post_link', 'schedule', 'prompt_template', 'news_source_display', 'created_at', 'generation_time', 'tokens_used']
    list_filter = ['schedule', 'prompt_template', 'created_at']
    search_fields = ['post__title', 'generated_title']
    readonly_fields = ['created_at', 'generation_time', 'tokens_used', 'news_source_display', 'sources_statistics_display']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('schedule', 'prompt_template', 'post', 'created_at')
        }),
        ('Источники новостей', {
            'fields': ('news_source_display', 'sources_statistics_display'),
        }),
        ('Сгенерированные данные', {
            'fields': ('generated_title', 'generated_description', 'generated_content', 'generated_image_prompt')
        }),
        ('Использованные промпты', {
            'fields': ('title_prompt_used', 'description_prompt_used', 'content_prompt_used', 'image_prompt_used'),
            'classes': ('collapse',)
        }),
        ('Ответы AI', {
            'fields': ('ai_title_response', 'ai_description_response', 'ai_content_response', 'ai_image_response'),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('context_data', 'generation_time', 'tokens_used'),
            'classes': ('collapse',)
        }),
    )
    
    def post_link(self, obj):
        """Ссылка на статью"""
        url = reverse('admin:Blog_post_change', args=[obj.post.pk])
        return format_html('<a href="{}">{}</a>', url, obj.post.title[:50])
    post_link.short_description = 'Статья'
    
    def news_source_display(self, obj):
        """Отображение источника новостей"""
        if obj.context_data and 'news_source' in obj.context_data:
            source_name = obj.context_data.get('news_source', 'Unknown')
            source_type = obj.context_data.get('news_source_type', 'unknown')
            return format_html(
                '<strong>{}</strong> <span class="text-gray-500">({})</span>',
                source_name,
                source_type.upper()
            )
        return '-'
    news_source_display.short_description = 'Источник новостей'
    
    def sources_statistics_display(self, obj):
        """Отображение статистики по источникам"""
        if obj.context_data and 'sources_statistics' in obj.context_data:
            stats = obj.context_data.get('sources_statistics', {})
            total = obj.context_data.get('total_news_found', 0)
            
            if not stats:
                return '-'
            
            html = []
            if total:
                html.append(f'<p class="mb-2"><strong>Всего найдено: {total}</strong></p>')
            
            html.append('<table class="table" style="width: 100%;">')
            html.append('<tr><th>Источник</th><th>Тип</th><th>Количество</th><th>%</th></tr>')
            
            for source_name, data in sorted(stats.items(), key=lambda x: x[1].get('count', 0), reverse=True):
                count = data.get('count', 0)
                percentage = data.get('percentage', 0.0)
                source_type = data.get('type', 'unknown')
                html.append(
                    f'<tr>'
                    f'<td>{source_name}</td>'
                    f'<td><span class="badge">{source_type.upper()}</span></td>'
                    f'<td><strong>{count}</strong></td>'
                    f'<td>{percentage:.1f}%</td>'
                    f'</tr>'
                )
            
            html.append('</table>')
            return format_html(''.join(html))
        return '-'
    sources_statistics_display.short_description = 'Статистика по источникам'


@admin.register(TokenUsage)
class TokenUsageAdmin(admin.ModelAdmin):
    list_display = ['date', 'model', 'total_tokens', 'prompt_tokens', 'completion_tokens', 'requests_count', 'cost']
    list_filter = ['date', 'model']
    search_fields = ['model']
    readonly_fields = ['date']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('date', 'model', 'requests_count')
        }),
        ('Использование токенов', {
            'fields': ('prompt_tokens', 'completion_tokens', 'total_tokens')
        }),
        ('Стоимость', {
            'fields': ('cost',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Записи создаются автоматически
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(NewsSearchSettings)
class NewsSearchSettingsAdmin(admin.ModelAdmin):
    """Одна запись id=1; основной UI — дашборд «Поиск новостей»."""

    list_display = ['id', 'updated_at']
    readonly_fields = ['id', 'updated_at']
    fieldsets = (
        ('DuckDuckGo', {'fields': ('ddg_search_url_template', 'ddg_query_suffix')}),
        (
            'Пул и таймауты',
            {'fields': ('search_per_source_limit', 'search_max_collect', 'search_pool_timeout', 'search_parallel_max')},
        ),
        (
            'Ранжирование и повтор',
            {
                'fields': (
                    'freshness_hours',
                    'penalize_unknown_published',
                    'rank_random_jitter',
                    'query_variant_suffixes',
                    'top_list_random_offset_max',
                    'force_fresh_news_on_content_retry',
                )
            },
        ),
        ('Служебное', {'fields': ('updated_at',), 'classes': ('collapse',)}),
    )

    def has_add_permission(self, request):
        return not NewsSearchSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NewsSearchEndpoint)
class NewsSearchEndpointAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'is_active', 'category', 'sort_order', 'created_at']
    list_filter = ['is_active', 'kind', 'category']
    search_fields = ['name', 'notes', 'search_url', 'rss_feed_url']
    list_editable = ['sort_order', 'is_active']
    ordering = ['sort_order', 'name']

    fieldsets = (
        ('Общее', {
            'fields': ('name', 'is_active', 'category', 'sort_order', 'notes'),
        }),
        ('HTML-скрапинг', {
            'fields': ('base_url', 'search_url', 'article_selector', 'title_selector'),
            'description': 'Для type=HTML: в search_url допустимы {query} и {category}.',
        }),
        ('RSS', {
            'fields': ('rss_feed_url',),
            'description': 'Для type=RSS: укажите rss_feed_url или search_url с {query}.',
        }),
    )


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ['source_name', 'source_type', 'articles_count', 'total_views', 'rating', 'last_used', 'is_active']
    list_filter = ['source_type', 'is_active', 'last_used']
    search_fields = ['source_name', 'source_url']
    readonly_fields = ['rating', 'created_at', 'updated_at']
    list_editable = ['is_active']
    date_hierarchy = 'last_used'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('source_name', 'source_url', 'source_type', 'is_active')
        }),
        ('Статистика', {
            'fields': ('articles_count', 'total_views', 'rating', 'last_used')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(CategoryStats)
class CategoryStatsAdmin(admin.ModelAdmin):
    list_display = ['category', 'articles_count', 'total_views', 'priority', 'last_publication']
    list_filter = ['last_publication', 'priority']
    search_fields = ['category__title']
    readonly_fields = ['priority', 'created_at', 'updated_at']
    date_hierarchy = 'last_publication'
    
    fieldsets = (
        ('Категория', {
            'fields': ('category',)
        }),
        ('Статистика', {
            'fields': ('articles_count', 'total_views', 'priority', 'last_publication')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at')
        }),
    )