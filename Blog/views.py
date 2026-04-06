from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from urllib.parse import quote
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Post, Category, Comment, PostLike
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import EmailPostForm, CommentForm, SearchForm, PostEditForm
from taggit.models import Tag
from urllib.parse import unquote
from django.db.models import Q, Count, F
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
import json

logger = logging.getLogger(__name__)


def post_list(request, category_slug=None):
    category = None
    
    # Получаем все категории с подсчетом статей
    all_categories = Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).filter(post_count__gt=0).order_by('tree_id', 'lft')
    
    # Разделяем на родительские и дочерние категории
    parent_categories = []
    child_categories = []
    
    for cat in all_categories:
        if cat.is_leaf_node():
            # Если это дочерняя категория, добавляем её в список дочерних
            child_categories.append(cat)
        else:
            # Если это родительская категория
            parent_categories.append(cat)
    
    posts = Post.objects.filter(status='published').annotate(
        comments_count=Count('comments', filter=Q(comments__active=True))
    ).order_by('-created')
    count_post = Post.objects.filter(status='published').count()
    
    # Фильтрация по параметрам запроса
    selected_category = request.GET.get('category')
    selected_tags = request.GET.getlist('tags')
    selected_author = request.GET.get('author')
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        # Только эта категория (без дочерних). Иначе у родителя вроде «Сайтостроение»
        # в списке оказываются статьи всех подтем — выглядит как «всё подряд».
        posts = posts.filter(category=category)
        zagolovok = 'Категория: ' + category.title
    elif selected_category:
        # Фильтрация по выбранной категории
        posts = posts.filter(category_id=selected_category)
        selected_cat = Category.objects.get(id=selected_category)
        zagolovok = f'Категория: {selected_cat.title}'
    elif selected_tags:
        # Фильтрация по выбранным тегам
        posts = posts.filter(tags__name__in=selected_tags).distinct()
        tag_names = [Tag.objects.get(name=tag).name for tag in selected_tags]
        zagolovok = f'Теги: {", ".join(tag_names)}'
    elif selected_author:
        # Фильтрация по автору
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            author = User.objects.get(id=selected_author)
            posts = posts.filter(author_id=selected_author)
            zagolovok = f'Автор: {author.get_full_name() or author.username}'
        except User.DoesNotExist:
            zagolovok = 'Все статьи'
    else:
        zagolovok = 'Все статьи'
    
    # Получаем теги в зависимости от выбранной категории (GET или страница по slug)
    if category:
        category_posts = Post.objects.filter(status='published', category=category)
        all_tags = Tag.objects.filter(
            taggit_taggeditem_items__content_type__model='post',
            taggit_taggeditem_items__object_id__in=category_posts.values_list('id', flat=True)
        ).annotate(
            post_count=Count('taggit_taggeditem_items', filter=Q(
                taggit_taggeditem_items__content_type__model='post',
                taggit_taggeditem_items__object_id__in=category_posts.values_list('id', flat=True)
            ))
        ).filter(post_count__gt=0).distinct().order_by('name')
    elif selected_category:
        # Если выбрана категория, показываем только теги из статей этой категории
        category_posts = Post.objects.filter(status='published', category_id=selected_category)
        all_tags = Tag.objects.filter(
            taggit_taggeditem_items__content_type__model='post',
            taggit_taggeditem_items__object_id__in=category_posts.values_list('id', flat=True)
        ).annotate(
            post_count=Count('taggit_taggeditem_items', filter=Q(
                taggit_taggeditem_items__content_type__model='post',
                taggit_taggeditem_items__object_id__in=category_posts.values_list('id', flat=True)
            ))
        ).filter(post_count__gt=0).distinct().order_by('name')
    else:
        # Общий список блога — все теги
        all_tags = Tag.objects.annotate(
            post_count=Count('taggit_taggeditem_items', filter=Q(taggit_taggeditem_items__content_type__model='post'))
        ).filter(post_count__gt=0).order_by('name')
    
    # Обновляем счетчик после фильтрации
    filtered_count = posts.count()
    
    # Генерируем structured data для категории или автора
    structured_data = None
    from .utils import generate_category_structured_data, generate_author_structured_data
    
    if category:
        # Structured data для категории
        structured_data = generate_category_structured_data(category, posts, request)
    elif selected_author:
        # Structured data для автора
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            author = User.objects.get(id=selected_author)
            structured_data = {'author': generate_author_structured_data(author, posts, request)}
        except User.DoesNotExist:
            pass
    
    return render(request,
                  'blog/page_blog-1.html',
                  {'category': category,
                   'parent_categories': parent_categories,
                   'child_categories': child_categories,
                   'all_categories': all_categories,
                   'all_tags': all_tags,
                   'selected_category': selected_category,
                   'selected_tags': selected_tags,
                   'posts': posts,
                   'zagolovok': zagolovok,
                   'count_post': count_post,
                   'filtered_count': filtered_count,
                   'structured_data': structured_data})


def _blog_staff_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _singl_page_context(request, post, comment_form, show_form, **extra):
    """Общий контекст для шаблона страницы статьи (page_singl-1 / singl-1)."""
    comments = post.comments.filter(active=True, parent=None).prefetch_related('children')
    user_liked = False
    if request.user.is_authenticated:
        user_liked = PostLike.objects.filter(post=post, user=request.user).exists()
    else:
        ip_address = get_client_ip(request)
        if ip_address:
            user_liked = PostLike.objects.filter(post=post, ip_address=ip_address).exists()

    comments_count = post.comments.filter(active=True).count()

    from .utils import get_related_posts, generate_article_structured_data, generate_table_of_contents
    from .utils import generate_faq_structured_data, generate_howto_structured_data

    related_posts = get_related_posts(post, limit=5)
    toc_html = None
    post_content_with_toc = post.content
    if post.content:
        toc_html, post_content_with_toc = generate_table_of_contents(post.content, min_headings=3)

    structured_data = generate_article_structured_data(post, request)
    faq_data = generate_faq_structured_data(post)
    howto_data = generate_howto_structured_data(post)
    if faq_data:
        structured_data['faq'] = json.dumps(faq_data, ensure_ascii=False)
    if howto_data:
        structured_data['howto'] = json.dumps(howto_data, ensure_ascii=False)

    ctx = {
        'post': post,
        'zagolovok': post.title,
        'comments': comments,
        'comments_count': comments_count,
        'comment_form': comment_form,
        'user_liked': user_liked,
        'show_comment_form': show_form,
        'related_posts': related_posts,
        'structured_data': structured_data,
        'toc_html': toc_html,
        'post_content_with_toc': post_content_with_toc,
    }
    ctx.update(extra)
    return ctx


def post_legacy_post_path_redirect(request, id):
    """
    Ссылки вида /blog/<id>/post/: часто ошибочно принимают «post» за тип страницы, тогда как
    в проекте второй сегмент — это slug (/blog/<id>/<slug>/). Редирект на канонический URL.
    Если slug статьи реально «post», отдаём страницу без редиректа (иначе 301-петля).
    """
    post = get_object_or_404(Post, pk=id)
    if post.slug != 'post':
        return HttpResponsePermanentRedirect(post.get_absolute_url())
    return post_detail(request, id, 'post')


def post_detail(request, id, slug=None):
    try:
        if slug:
            post = get_object_or_404(Post, id=id, slug=slug)
        else:
            post = get_object_or_404(Post, id=id)
            if post.slug:
                return HttpResponseRedirect(post.get_absolute_url())
        
        # Инкрементируем просмотры (только для GET запросов и не для AJAX)
        if request.method == 'GET' and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            # Используем F() для атомарного обновления
            Post.objects.filter(id=post.id).update(views=F('views') + 1)
            # Обновляем объект post для отображения
            post.refresh_from_db()
            
            # Обновляем статистику категории
            if post.category:
                try:
                    from Assistant.models import CategoryStats
                    stats, created = CategoryStats.objects.get_or_create(
                        category=post.category,
                        defaults={'total_views': 0, 'articles_count': 0, 'priority': 1.0}
                    )
                    stats.total_views += 1
                    # Обновляем приоритет: чем больше просмотров на статью, тем выше приоритет
                    if stats.articles_count > 0:
                        stats.priority = (stats.total_views / stats.articles_count) * 0.1 + stats.articles_count * 0.01
                    stats.save(update_fields=['total_views', 'priority'])
                except Exception as e:
                    logger.warning(f"Ошибка обновления статистики категории: {str(e)}")

        if request.method == 'POST':
            try:
                if not request.user.is_authenticated:
                    login_url = reverse('identity_auth:customer_login')
                    next_q = quote(request.get_full_path(), safe='/')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': 'Войдите, чтобы оставить комментарий.',
                            'login_required': True,
                        }, status=403)
                    messages.info(request, 'Войдите, чтобы оставить комментарий.')
                    return HttpResponseRedirect(f'{login_url}?next={next_q}')

                # A comment was posted
                parent_comment_id = request.POST.get('parent_comment_id')
                parent_comment = None
                
                if parent_comment_id:
                    try:
                        parent_comment = Comment.objects.get(id=parent_comment_id, active=True, post=post)
                    except Comment.DoesNotExist:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': 'Родительский комментарий не найден.'
                            }, status=400)
                        else:
                            messages.error(request, 'Родительский комментарий не найден.')
                            parent_comment = None
                
                comment_form = CommentForm(
                    data=request.POST,
                    parent_comment=parent_comment,
                    user=request.user,
                )
                if comment_form.is_valid():
                    try:
                        logger.info(f"[COMMENT_SAVE] Начало сохранения комментария. Post ID: {post.id}, Parent: {parent_comment.id if parent_comment else None}")
                        
                        # Create Comment object but don't save to database yet
                        new_comment = comment_form.save(commit=False)
                        logger.info(f"[COMMENT_SAVE] Форма валидна, объект создан. Author: {new_comment.author_comment}, Content length: {len(new_comment.content)}")
                        
                        # Assign the current post to the comment
                        new_comment.post = post
                        new_comment.parent = parent_comment
                        
                        # Save the comment to the database (MPTT автоматически обновит поля)
                        new_comment.save()
                        logger.info(f"[COMMENT_SAVE] Комментарий сохранен в БД. Comment ID: {new_comment.id}")
                        
                        # Проверяем, не был ли комментарий удален модерацией
                        # Обновляем объект из БД, чтобы проверить его существование
                        try:
                            new_comment.refresh_from_db()
                            logger.info(f"[COMMENT_SAVE] Комментарий {new_comment.id} успешно обновлен из БД. Active: {new_comment.active}")
                        except Comment.DoesNotExist:
                            # Комментарий был удален модерацией
                            logger.warning(f"[COMMENT_SAVE] Комментарий был удален модерацией после сохранения. Comment ID был: {getattr(new_comment, 'id', 'unknown')}")
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'message': 'Сообщение не опубликовано.',
                                    'deleted': True
                                }, status=400)
                            else:
                                messages.warning(request, 'Сообщение не опубликовано.')
                                return HttpResponseRedirect(post.get_absolute_url() + '#comments')
                        
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            # AJAX запрос - возвращаем JSON с данными нового комментария
                            try:
                                comment_data = {
                                    'id': new_comment.id,
                                    'author_comment': new_comment.author_comment,
                                    'content': new_comment.content,
                                    'created': new_comment.created.strftime('%d.%m.%Y %H:%M'),
                                    'is_admin_reply': new_comment.is_admin_reply,
                                    'parent_id': parent_comment.id if parent_comment else None,
                                    'is_reply': parent_comment is not None
                                }
                                logger.info(f"[COMMENT_SAVE] Формирование JSON ответа. Comment ID: {new_comment.id}, Is reply: {comment_data['is_reply']}")
                                
                                return JsonResponse({
                                    'success': True,
                                    'message': 'Комментарий добавлен успешно!',
                                    'comment': comment_data
                                })
                            except Exception as e:
                                logger.error(f"[COMMENT_SAVE] Ошибка при формировании JSON ответа для комментария {new_comment.id}: {str(e)}", exc_info=True)
                                return JsonResponse({
                                    'success': False,
                                    'message': f'Ошибка при формировании ответа: {str(e)}'
                                }, status=500)
                        else:
                            messages.success(request, 'Комментарий добавлен успешно!')
                            logger.info(f"[COMMENT_SAVE] Комментарий {new_comment.id} успешно сохранен (обычный запрос)")
                            return HttpResponseRedirect(post.get_absolute_url() + '#comments')
                    except Exception as e:
                        logger.error(f"[COMMENT_SAVE] КРИТИЧЕСКАЯ ОШИБКА при сохранении комментария. Post ID: {post.id}, Error: {str(e)}", exc_info=True)
                        raise  # Пробрасываем дальше для общего обработчика
                else:
                    # Форма невалидна
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        # Преобразуем ошибки формы в читаемый формат
                        errors_dict = {}
                        for field, error_list in comment_form.errors.items():
                            errors_dict[field] = [str(error) for error in error_list]
                        
                        return JsonResponse({
                            'success': False,
                            'errors': errors_dict,
                            'message': 'Пожалуйста, исправьте ошибки в форме.'
                        }, status=400)
                    else:
                        # Обычная форма с ошибками
                        messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
            except Exception as e:
                logger.error(f"Ошибка при сохранении комментария: {str(e)}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Произошла ошибка при сохранении комментария: {str(e)}'
                    }, status=500)
                else:
                    messages.error(request, f'Произошла ошибка при сохранении комментария: {str(e)}')
        else:
            if request.user.is_authenticated:
                comment_form = CommentForm(user=request.user)
            else:
                comment_form = None

        # Если форма была отправлена с ошибками (не AJAX), показываем её открытой
        show_form = False
        if (
            request.method == 'POST'
            and request.user.is_authenticated
            and request.headers.get('X-Requested-With') != 'XMLHttpRequest'
        ):
            if comment_form is not None and hasattr(comment_form, 'errors') and comment_form.errors:
                show_form = True

        return render(
            request,
            'blog/page_singl-1.html',
            _singl_page_context(request, post, comment_form, show_form),
        )
    except Http404:
        logger.error(f"Post not found: id={id}, slug={slug}")
        # Try to find the post by ID only
        try:
            post = Post.objects.get(id=id)
            # If found by ID but slug is different, redirect to correct URL
            if post.slug != slug:
                return HttpResponseRedirect(post.get_absolute_url())
        except Post.DoesNotExist:
            pass
        raise Http404("Статья не найдена. Возможно, она была удалена или перемещена.")


@login_required
@user_passes_test(_blog_staff_user)
@require_http_methods(['GET'])
def post_staff_preview(request, id, slug):
    """
    Предпросмотр статьи для персонала (включая черновики): вёрстка как на сайте,
    без накрутки счётчика просмотров. Параметр next — URL «Назад» (список модерации и т.п.).
    """
    post = get_object_or_404(Post, id=id, slug=slug)
    back_url = request.GET.get('next') or reverse('moderation:article_list')
    comment_form = CommentForm(user=request.user) if request.user.is_authenticated else None
    return render(
        request,
        'blog/page_singl-1.html',
        _singl_page_context(
            request,
            post,
            comment_form,
            False,
            staff_article_preview=True,
            staff_preview_back_url=back_url,
        ),
    )


def post_list_by_tag(request, tag_slug=None):
    tag = None
    
    # Получаем все категории с подсчетом статей
    all_categories = Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).filter(post_count__gt=0).order_by('tree_id', 'lft')
    
    # Разделяем на родительские и дочерние категории
    parent_categories = []
    child_categories = []
    
    for cat in all_categories:
        if cat.is_leaf_node():
            # Если это дочерняя категория, добавляем её в список дочерних
            child_categories.append(cat)
        else:
            # Если это родительская категория
            parent_categories.append(cat)
    
    posts = Post.objects.filter(status='published').annotate(
        comments_count=Count('comments', filter=Q(comments__active=True))
    )
    count_post = posts.count()
    
    if tag_slug:
        # Расшифруйте тег slug, закодированный в URL-адресе
        decoded_slug = unquote(tag_slug)
        # Попробуйте найти тег по имени, а не по slug
        tag = get_object_or_404(Tag, name=decoded_slug)
        posts = posts.filter(tags__in=[tag])
    
    zagolovok = 'Тема: ' + tag.name
    return render(request,
                  'blog/page_blog-1.html',
                  {'tag': tag,
                   'zagolovok': zagolovok,
                   'parent_categories': parent_categories,
                   'child_categories': child_categories,
                   'all_categories': all_categories,
                   'posts': posts,
                   'count_post': count_post})


def post_search(request):
    form = SearchForm()
    query = None
    results = []
    
    # Получаем все категории с подсчетом статей
    all_categories = Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).filter(post_count__gt=0).order_by('tree_id', 'lft')
    
    # Разделяем на родительские и дочерние категории
    parent_categories = []
    child_categories = []
    
    for cat in all_categories:
        if cat.is_leaf_node():
            # Если это дочерняя категория, добавляем её в список дочерних
            child_categories.append(cat)
        else:
            # Если это родительская категория
            parent_categories.append(cat)
    
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            # Search in title, content, and description
            results = Post.objects.filter(
                Q(title__icontains=query) |
                Q(content__icontains=query) |
                Q(description__icontains=query)
            ).filter(status='published').annotate(
                comments_count=Count('comments', filter=Q(comments__active=True))
            ).distinct()
    
    return render(request,
                 'blog/search.html',
                 {'form': form,
                  'query': query,
                  'results': results,
                  'parent_categories': parent_categories,
                  'child_categories': child_categories,
                  'all_categories': all_categories,
                  'zagolovok': f'Поиск: {query}' if query else 'Поиск'})


def filter_posts_ajax(request):
    """API endpoint для фильтрации статей через AJAX без перезагрузки страницы"""
    if request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        category_id = request.GET.get('category')
        
        # Получаем все опубликованные статьи
        posts = Post.objects.filter(status='published').annotate(
            comments_count=Count('comments', filter=Q(comments__active=True))
        ).order_by('-created')
        
        # Фильтруем по категории, если выбрана
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                posts = posts.filter(category=category)
                zagolovok = f'Категория: {category.title}'
            except Category.DoesNotExist:
                zagolovok = 'Все статьи'
        else:
            zagolovok = 'Все статьи'
        
        # Подготавливаем данные статей для JSON
        posts_data = []
        for post in posts:
            posts_data.append({
                'id': post.id,
                'title': post.title,
                'slug': post.slug,
                'url': post.get_absolute_url(),
                'created': post.created.strftime('%d.%m.%Y'),
                'views': post.views,
                'likes_count': post.likes_count,
                'category': post.category.title,
                'category_id': post.category.id,
                'fixed': post.fixed,
                'image_url': post.kartinka.url if post.kartinka else None,
                'video_file_url': post.video_file.url if post.video_file else None,
                'has_video': bool(post.video) or bool(post.video_file),
                'tags': [tag.name for tag in post.tags.all()],
                'tags_count': post.tags.count(),
                'comments_count': post.comments_count
            })
        
        return JsonResponse({
            'success': True,
            'posts': posts_data,
            'zagolovok': zagolovok,
            'count': len(posts_data)
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@user_passes_test(_blog_staff_user)
def post_edit(request, id, slug):
    """Страница редактирования статьи (staff / суперюзер — как доступ к панели модерации)"""
    post = get_object_or_404(Post, id=id, slug=slug)

    if request.method == 'POST' and request.POST.get('reset_and_repost_vk'):
        post.vk_posted_at = None
        post.vk_wall_post_id = None
        post.save(update_fields=['vk_posted_at', 'vk_wall_post_id'])
        messages.success(
            request,
            'Метки публикации ВК сброшены и снова вызвана отправка на стену '
            '(при статусе «Опубликовано» и настроенном токене). Проверьте блок «ВКонтакте» ниже.',
        )
        return redirect('Blog:post_edit', id=post.id, slug=post.slug)

    if request.method == 'POST':
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            # Сохраняем информацию о том, кто обновил статью
            post = form.save(commit=False)
            post.updater = request.user
            post.save()
            form.save_m2m()  # Сохраняем теги
            
            messages.success(request, 'Статья успешно обновлена!')
            return redirect('Blog:post_detail', id=post.id, slug=post.slug)
        else:
            # Логируем ошибки формы для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[POST_EDIT] Ошибки валидации формы для статьи {post.id}:")
            for field, errors in form.errors.items():
                logger.error(f"  {field}: {errors}")
            if form.non_field_errors():
                logger.error(f"  Общие ошибки: {form.non_field_errors()}")
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = PostEditForm(instance=post)
    
    # Получаем все категории для отображения
    all_categories = Category.objects.all()
    
    return render(request, 'blog/post_edit.html', {
        'post': post,
        'form': form,
        'all_categories': all_categories,
        'zagolovok': f'Редактирование: {post.title}'
    })


def get_client_ip(request):
    """Получение IP адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_POST
def post_like(request, post_id):
    """Обработка лайка/дизлайка статьи"""
    try:
        post = get_object_or_404(Post, id=post_id)
        
        # Определяем пользователя или IP
        user = request.user if request.user.is_authenticated else None
        ip_address = get_client_ip(request) if not user else None
        
        # Проверяем, есть ли уже лайк
        if user:
            # Для авторизованных пользователей проверяем по user
            try:
                like = PostLike.objects.get(post=post, user=user)
                created = False
            except PostLike.DoesNotExist:
                like = PostLike.objects.create(post=post, user=user)
                created = True
        else:
            # Для неавторизованных пользователей проверяем по IP
            if not ip_address:
                return JsonResponse({'success': False, 'error': 'Не удалось определить IP адрес'}, status=400)
            try:
                like = PostLike.objects.get(post=post, ip_address=ip_address, user__isnull=True)
                created = False
            except PostLike.DoesNotExist:
                like = PostLike.objects.create(post=post, ip_address=ip_address)
                created = True
        
        if created:
            # Лайк добавлен
            Post.objects.filter(id=post.id).update(likes_count=F('likes_count') + 1)
            post.refresh_from_db()
            return JsonResponse({
                'success': True,
                'liked': True,
                'likes_count': post.likes_count,
                'message': 'Статья понравилась!'
            })
        else:
            # Лайк уже был, удаляем его (дизлайк)
            like.delete()
            Post.objects.filter(id=post.id).update(likes_count=F('likes_count') - 1)
            post.refresh_from_db()
            return JsonResponse({
                'success': True,
                'liked': False,
                'likes_count': post.likes_count,
                'message': 'Лайк удалён'
            })
    except Exception as e:
        logger.error(f"Error in post_like: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
def increment_views(request, post_id):
    """API для инкремента просмотров (для AJAX запросов)"""
    try:
        post = get_object_or_404(Post, id=post_id)
        Post.objects.filter(id=post.id).update(views=F('views') + 1)
        post.refresh_from_db()
        return JsonResponse({
            'success': True,
            'views': post.views
        })
    except Exception as e:
        logger.error(f"Error in increment_views: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


