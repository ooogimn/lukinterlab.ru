from django.urls import path
from . import views

app_name = 'moderation'

urlpatterns = [
    path('', views.moderation_dashboard, name='dashboard'),
    path('articles/', views.article_moderation_list, name='article_list'),
    path('articles/<int:moderation_id>/', views.article_moderation_detail, name='article_detail'),
    path('comments/', views.comment_moderation_list, name='comment_list'),
    path('comments/moderation/<int:moderation_id>/delete/', views.comment_moderation_delete, name='comment_moderation_delete'),
    path('comments/<int:comment_id>/edit/', views.comment_edit, name='comment_edit'),
    path('comments/criteria/create/', views.comment_criteria_create, name='comment_criteria_create'),
    path('comments/criteria/<int:criteria_id>/edit/', views.comment_criteria_edit, name='comment_criteria_edit'),
    path('comments/criteria/<int:criteria_id>/toggle/', views.comment_criteria_toggle, name='comment_criteria_toggle'),
    path('comments/criteria/<int:criteria_id>/delete/', views.comment_criteria_delete, name='comment_criteria_delete'),
    path('seo/', views.seo_analysis_list, name='seo_list'),
    path('seo/<int:analysis_id>/', views.seo_analysis_detail, name='seo_detail'),
    path('statistics/', views.statistics_view, name='statistics'),
]

