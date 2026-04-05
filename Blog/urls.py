from django.urls import path
from .views import *

app_name = 'Blog'

urlpatterns = [
    path('', post_list, name='post_list'),
    path('search/', post_search, name='post_search'),
    path('tag/<str:tag_slug>/', post_list_by_tag, name='post_list_by_tag'),
    # До общего <id>/<slug>/: иначе /blog/80/post/ парсится как slug="post" и даёт 404 при несовпадении slug в БД
    path('<int:id>/post/', post_legacy_post_path_redirect, name='post_detail_legacy_post_path'),
    path('<int:id>/<slug:slug>/preview/', post_staff_preview, name='post_staff_preview'),
    path('<int:id>/<slug:slug>/edit/', post_edit, name='post_edit'),
    path('<int:id>/<slug:slug>/', post_detail, name='post_detail'),
    path('<slug:category_slug>/', post_list, name='post_list_by_category'),
    path('api/filter-posts/', filter_posts_ajax, name='filter_posts_ajax'),
    path('api/post/<int:post_id>/like/', post_like, name='post_like'),
    path('api/post/<int:post_id>/increment-views/', increment_views, name='increment_views'),
]
