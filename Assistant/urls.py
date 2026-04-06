from django.urls import path
from . import views
from . import dashboard_views

app_name = 'assistant'

urlpatterns = [
    # API для чата
    path('api/chat/', views.ChatAPIView.as_view(), name='chat_api'),
    path('api/feedback/', views.feedback_api, name='feedback_api'),
    path('api/analytics/', views.analytics_api, name='analytics_api'),
    path('api/settings/', views.settings_api, name='settings_api'),
    # Telegram webhook
    path('api/telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
    # API для получения новых сообщений
    path('api/messages/', views.get_new_messages_api, name='get_messages_api'),
    
    # Дашборд автопостинга
    path('dashboard/', dashboard_views.dashboard_main, name='dashboard_main'),
    path('dashboard/templates/', dashboard_views.templates_list, name='dashboard_templates'),
    path('dashboard/templates/create/', dashboard_views.template_create, name='dashboard_template_create'),
    path('dashboard/templates/<int:pk>/edit/', dashboard_views.template_edit, name='dashboard_template_edit'),
    path('dashboard/templates/<int:pk>/test/', dashboard_views.template_test, name='dashboard_template_test'),
    path('dashboard/templates/<int:pk>/test/generate/', dashboard_views.template_test_generate, name='dashboard_template_test_generate'),
    path('dashboard/templates/<int:pk>/preview/', dashboard_views.template_preview_prompts, name='dashboard_template_preview'),
    path('dashboard/templates/<int:pk>/variables/', dashboard_views.template_test_variables, name='dashboard_template_variables'),
    path('dashboard/generation-progress/<str:progress_id>/', dashboard_views.template_generation_progress, name='dashboard_generation_progress'),
    path('dashboard/templates/<int:pk>/delete/', dashboard_views.template_delete, name='dashboard_template_delete'),
    path('dashboard/posts/<int:post_id>/publish/', dashboard_views.template_test_publish, name='dashboard_post_publish'),
    path('dashboard/posts/<int:post_id>/draft/', dashboard_views.template_test_draft, name='dashboard_post_draft'),
    path('dashboard/posts/<int:post_id>/schedule/', dashboard_views.template_test_schedule, name='dashboard_post_schedule'),
    path('dashboard/posts/<int:post_id>/delete/', dashboard_views.template_test_delete, name='dashboard_post_delete'),
    path('dashboard/schedules/', dashboard_views.schedules_list, name='dashboard_schedules'),
    path('dashboard/schedules/create/', dashboard_views.schedule_create, name='dashboard_schedule_create'),
    path('dashboard/schedules/<int:pk>/edit/', dashboard_views.schedule_edit, name='dashboard_schedule_edit'),
    path('dashboard/schedules/<int:pk>/delete/', dashboard_views.schedule_delete, name='dashboard_schedule_delete'),
    path('dashboard/schedules/<int:pk>/run/', dashboard_views.schedule_run_now, name='dashboard_schedule_run'),
    path('dashboard/history/', dashboard_views.history_list, name='dashboard_history'),
    path('dashboard/history/<int:pk>/', dashboard_views.history_detail, name='dashboard_history_detail'),
    path('dashboard/history/clear/', dashboard_views.history_clear, name='dashboard_history_clear'),
    path('dashboard/history/delete-selected/', dashboard_views.history_delete_selected, name='dashboard_history_delete_selected'),
    path('dashboard/monitoring/', dashboard_views.monitoring, name='dashboard_monitoring'),
    path(
        'dashboard/news-search/',
        dashboard_views.dashboard_news_search_settings,
        name='dashboard_news_search_settings',
    ),
    path('dashboard/api/statistics/', dashboard_views.api_statistics, name='dashboard_api_statistics'),
]
