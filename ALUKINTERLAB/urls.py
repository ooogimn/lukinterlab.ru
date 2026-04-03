from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from django.views.static import serve
from home.sitemaps import (
    StaticViewSitemap, BlogPostSitemap, BlogCategorySitemap,
    OtzivSitemap, RabotaSitemap
)
from Blog.feeds import LatestPostsFeed, LatestPostsRSSFeed
from Blog.vk_callback import vk_group_callback

# Sitemap configuration
sitemaps = {
    'static': StaticViewSitemap,
    'blog_posts': BlogPostSitemap,
    'blog_categories': BlogCategorySitemap,
    'otzivs': OtzivSitemap,
    'rabotas': RabotaSitemap,
}

urlpatterns = [
    # Без финального / — как в кабинете VK; иначе POST для confirm уходит в редирект и ломается.
    path('callback/<str:slug>', vk_group_callback, name='vk_group_callback'),
    path('callback/<str:slug>/', vk_group_callback, name='vk_group_callback_slash'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    # Раньше кастомные дашборды жили под /admin/... и конфликтовали с admin.site.urls;
    # теперь они на префиксе /manage/ в home.urls. Порядок «сначала home» оставляем — безопасно.
    path('', include('home.urls')),
    path('admin/', admin.site.urls),
    path('blog/', include('Blog.urls', namespace='Blog')),
    path('assistant/', include('Assistant.urls', namespace='assistant')),
    path('moderation/', include('Moderation.urls', namespace='moderation')),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    # RSS Feeds
    path('blog/feed/', LatestPostsFeed(), name='blog_feed'),
    path('blog/rss/', LatestPostsRSSFeed(), name='blog_rss'),
]

# Раздача медиа-файлов (работает и в продакшене, если веб-сервер не настроен)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Продакшен: медиа и статика через Django, если веб-сервер не отдаёт /media/ и /static/
    # (иначе админка/Jazzmin без CSS при DEBUG=False). Идеально — alias в Apache/Nginx.
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]