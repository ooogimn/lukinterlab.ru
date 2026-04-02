from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import json
import logging
from Blog.models import Post, Comment
from Blog.forms import PostEditForm

logger = logging.getLogger(__name__)
from .models import (
    ArticleModeration, CommentModeration,
    SEOAnalysis, ModerationCriteria, CommentModerationCriteria,
    ModerationStatistics
)
from .services import StatisticsService
from .forms import CommentModerationCriteriaForm
from django.db import transaction
from django.db.models import Count
from django.contrib.contenttypes.prefetch import GenericPrefetch

from home.models import OtzivComment, OrderComment


def is_moderator(user):
    """Проверка прав модератора"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# Черновики, по которым модерация ещё не «одобрена» (реальная очередь работы)
def _articles_moderation_queue_qs():
    return (
        ArticleModeration.objects.filter(post__status='draft')
        .exclude(status='approved')
        .select_related('post', 'post__category', 'post__author', 'moderator', 'criteria_used')
    )


@login_required
@user_passes_test(is_moderator)
def moderation_dashboard(request):
    """Дашборд модерации"""
    pending_comments = CommentModeration.objects.filter(action__isnull=True).count()

    # Очередь: только черновики, где модерация не одобрена (не путать с «виснущими» pending у опубликованных)
    articles_in_moderation_queue = _articles_moderation_queue_qs().count()
    stale_moderation_count = ArticleModeration.objects.filter(
        post__status='published',
        status__in=('pending', 'needs_revision'),
    ).count()

    # Статистика по статусам (все записи в БД)
    articles_stats = {
        'pending': ArticleModeration.objects.filter(status='pending').count(),
        'approved': ArticleModeration.objects.filter(status='approved').count(),
        'rejected': ArticleModeration.objects.filter(status='rejected').count(),
        'needs_revision': ArticleModeration.objects.filter(status='needs_revision').count(),
    }

    recent_articles = _articles_moderation_queue_qs().order_by('-submitted_at')[:10]
    
    # Последние комментарии на модерации
    # Примечание: 'comment' - это GenericForeignKey, его нельзя использовать в select_related
    recent_comments = CommentModeration.objects.filter(action__isnull=True).select_related('content_type', 'criteria_used')[:10]
    
    # Статистика за последние 7 дней
    from datetime import timedelta
    from django.utils import timezone
    stats_service = StatisticsService()
    week_ago = timezone.now().date() - timedelta(days=7)
    today = timezone.now().date()
    period_stats = stats_service.get_statistics_period(week_ago, today)
    
    # Непрочитанные уведомления
    unread_notifications = request.user.moderation_notifications.filter(is_read=False).count()
    
    context = {
        'pending_articles': articles_in_moderation_queue,
        'stale_moderation_count': stale_moderation_count,
        'pending_comments': pending_comments,
        'articles_stats': articles_stats,
        'recent_articles': recent_articles,
        'recent_comments': recent_comments,
        'period_stats': period_stats,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'moderation/dashboard.html', context)


@login_required
@user_passes_test(is_moderator)
def article_moderation_list(request):
    """Список статей на модерации.

    По умолчанию — «рабочий» список: без уже опубликованных и одобренных (не дублируем старый архив).
    ?archive=1 — полный архив. ?queue=1 — очередь черновиков без одобрения.
    """
    status_param = request.GET.get('status')
    queue_only = request.GET.get('queue') == '1'
    archive = request.GET.get('archive') == '1'

    base = ArticleModeration.objects.select_related(
        'post', 'post__category', 'moderator', 'criteria_used',
    )

    if queue_only:
        articles = _articles_moderation_queue_qs()
    elif status_param:
        articles = base.filter(status=status_param)
        if not archive:
            articles = articles.exclude(post__status='published', status='approved')
    elif archive:
        articles = base.all()
    else:
        articles = base.exclude(post__status='published', status='approved')

    paginator = Paginator(articles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_filter': status_param or '',
        'queue_only': queue_only,
        'archive': archive,
        'status_choices': ArticleModeration.STATUS_CHOICES,
    }
    return render(request, 'moderation/article_list.html', context)


@login_required
@user_passes_test(is_moderator)
@require_http_methods(["POST"])
def article_post_delete(request, post_id):
    """Удаление статьи и связанной карточки ArticleModeration (CASCADE)."""
    post = get_object_or_404(Post, pk=post_id)
    title = post.title
    post.delete()
    messages.success(request, f'Статья «{title}» удалена.')
    return redirect('moderation:article_list')


@login_required
@user_passes_test(is_moderator)
def comment_moderation_list(request):
    """Список комментариев на модерации"""
    action_filter = request.GET.get('action', 'all')
    comment_type_filter = request.GET.get('type', 'all')
    
    # Базовый queryset
    if action_filter == 'all':
        comments = CommentModeration.objects.all()
    elif action_filter == 'pending':
        comments = CommentModeration.objects.filter(action__isnull=True)
    else:
        comments = CommentModeration.objects.filter(action=action_filter)
    
    # Фильтр по типу комментария
    if comment_type_filter != 'all':
        comments = comments.filter(comment_type=comment_type_filter)
    
    # GenericForeignKey «comment» — только через GenericPrefetch (не «content_object»).
    comments = comments.select_related('content_type', 'criteria_used').prefetch_related(
        GenericPrefetch(
            'comment',
            [
                Comment.objects.select_related('post', 'post__category'),
                OtzivComment.objects.select_related('otziv'),
                OrderComment.objects.select_related('order', 'author'),
            ],
        )
    )
    
    # Пагинация
    paginator = Paginator(comments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем список критериев с подсчетом обработанных комментариев
    criteria_list = CommentModerationCriteria.objects.annotate(
        processed_count=Count('commentmoderation')
    ).order_by('-created')
    
    context = {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'action_choices': CommentModeration.ACTION_CHOICES,
        'criteria_list': criteria_list,
    }
    return render(request, 'moderation/comment_list.html', context)


@login_required
@user_passes_test(is_moderator)
@require_http_methods(["POST"])
def comment_moderation_delete(request, moderation_id):
    """
    Удалить запись CommentModeration и связанный комментарий (Blog / отзыв / заказ).
    Для MPTT-дерева удаляется узел и потомки; ответы администратора под комментарием уходят вместе с ним.
    """
    try:
        with transaction.atomic():
            moderation = get_object_or_404(CommentModeration, pk=moderation_id)
            content_type = moderation.content_type
            object_id = moderation.object_id
            comment_obj = moderation.comment
            moderation.delete()
            if comment_obj is not None:
                comment_obj.delete()
            elif content_type is not None and object_id:
                # Если GFK в шаблоне/ORM не вернул объект — всё равно снести строку комментария в БД
                # (со страницы статьи он пропадёт).
                model = content_type.model_class()
                if model is not None:
                    try:
                        orphan = model.objects.get(pk=object_id)
                    except model.DoesNotExist:
                        orphan = None
                    if orphan is not None:
                        orphan.delete()
        return JsonResponse(
            {
                "success": True,
                "message": "Комментарий и запись модерации удалены.",
            }
        )
    except Exception as e:
        logger.error(
            "Ошибка удаления модерации комментария id=%s: %s",
            moderation_id,
            str(e),
            exc_info=True,
        )
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500,
        )


@login_required
@user_passes_test(is_moderator)
def seo_analysis_list(request):
    """Список SEO анализов"""
    seo_analyses = SEOAnalysis.objects.all().select_related('post').order_by('-analyzed_at')
    
    # Фильтр по оценке
    score_filter = request.GET.get('score', 'all')
    if score_filter == 'high':
        seo_analyses = seo_analyses.filter(seo_score__gte=80)
    elif score_filter == 'medium':
        seo_analyses = seo_analyses.filter(seo_score__gte=50, seo_score__lt=80)
    elif score_filter == 'low':
        seo_analyses = seo_analyses.filter(seo_score__lt=50)
    
    # Пагинация
    paginator = Paginator(seo_analyses, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'score_filter': score_filter,
    }
    return render(request, 'moderation/seo_list.html', context)


@login_required
@user_passes_test(is_moderator)
def seo_analysis_detail(request, analysis_id):
    """Детальная страница SEO анализа"""
    analysis = get_object_or_404(SEOAnalysis, id=analysis_id)
    
    context = {
        'analysis': analysis,
        'post': analysis.post,
    }
    return render(request, 'moderation/seo_detail.html', context)


@login_required
@user_passes_test(is_moderator)
def statistics_view(request):
    """Страница статистики модерации"""
    from datetime import timedelta
    from django.utils import timezone
    
    # Период по умолчанию - последние 30 дней
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    stats_service = StatisticsService()
    period_stats = stats_service.get_statistics_period(start_date, end_date)
    
    # Детальная статистика по дням
    daily_stats = ModerationStatistics.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    context = {
        'period_stats': period_stats,
        'daily_stats': daily_stats,
        'start_date': start_date,
        'end_date': end_date,
        'days': days,
    }
    return render(request, 'moderation/statistics.html', context)


@login_required
@user_passes_test(is_moderator)
@require_http_methods(["POST"])
def comment_edit(request, comment_id):
    """Универсальное редактирование комментария через AJAX (для всех типов)"""
    try:
        from django.contrib.contenttypes.models import ContentType
        
        # Получаем тип комментария из параметра или пробуем определить
        content_type_str = request.POST.get('content_type') or request.GET.get('content_type')
        
        if content_type_str:
            # Парсим строку типа "blog.comment"
            app_label, model = content_type_str.split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model)
            comment = content_type.get_object_for_this_type(id=comment_id)
        else:
            # По умолчанию пробуем Comment (Blog)
            try:
                comment = Comment.objects.get(id=comment_id)
            except Comment.DoesNotExist:
                # Пробуем другие типы
                from home.models import OtzivComment, OrderComment
                try:
                    comment = OtzivComment.objects.get(id=comment_id)
                except OtzivComment.DoesNotExist:
                    try:
                        comment = OrderComment.objects.get(id=comment_id)
                    except OrderComment.DoesNotExist:
                        return JsonResponse({
                            'success': False,
                            'error': 'Комментарий не найден'
                        }, status=404)
        
        # Получаем данные из JSON
        try:
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body.decode('utf-8'))
                new_content = data.get('content', '').strip()
            else:
                new_content = request.POST.get('content', '').strip()
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Ошибка при парсинге JSON: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Ошибка формата данных'
            }, status=400)
        
        if not new_content:
            return JsonResponse({
                'success': False,
                'error': 'Текст комментария не может быть пустым'
            }, status=400)
        
        # Обновляем комментарий
        comment.content = new_content
        comment.save(update_fields=['content'])
        
        # Обновляем запись модерации, если она существует (универсальный способ)
        try:
            from django.contrib.contenttypes.models import ContentType
            content_type = ContentType.objects.get_for_model(comment)
            moderation = CommentModeration.objects.filter(
                content_type=content_type,
                object_id=comment_id
            ).first()
            if moderation:
                # Очищаем исправленный текст, так как комментарий был отредактирован вручную
                moderation.corrected_text = ''
                moderation.save(update_fields=['corrected_text'])
        except Exception as e:
            logger.warning(f"Не удалось обновить запись модерации для комментария {comment_id}: {str(e)}")
            pass
        
        return JsonResponse({
            'success': True,
            'message': 'Комментарий успешно обновлен',
            'content': comment.content
        })
        
    except Exception as e:
        logger.error(f"Ошибка при редактировании комментария {comment_id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при сохранении: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_moderator)
def comment_criteria_create(request):
    """Создание критерия модерации комментариев"""
    if request.method == 'POST':
        form = CommentModerationCriteriaForm(request.POST)
        if form.is_valid():
            try:
                criteria = form.save()
                messages.success(request, f'Критерий "{criteria.name}" успешно создан!')
                return redirect('moderation:comment_list')
            except Exception as e:
                messages.error(request, f'Ошибка при сохранении: {str(e)}')
        else:
            # Показываем ошибки валидации
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CommentModerationCriteriaForm()
    
    context = {
        'form': form,
        'title': 'Создать критерий модерации комментариев',
    }
    return render(request, 'moderation/comment_criteria_form.html', context)


@login_required
@user_passes_test(is_moderator)
def comment_criteria_edit(request, criteria_id):
    """Редактирование критерия модерации комментариев"""
    criteria = get_object_or_404(CommentModerationCriteria, id=criteria_id)
    
    if request.method == 'POST':
        form = CommentModerationCriteriaForm(request.POST, instance=criteria)
        if form.is_valid():
            criteria = form.save()
            messages.success(request, f'Критерий "{criteria.name}" успешно обновлен!')
            return redirect('moderation:comment_list')
    else:
        form = CommentModerationCriteriaForm(instance=criteria)
    
    context = {
        'form': form,
        'criteria': criteria,
        'title': f'Редактировать критерий: {criteria.name}',
    }
    return render(request, 'moderation/comment_criteria_form.html', context)


@login_required
@user_passes_test(is_moderator)
def comment_criteria_toggle(request, criteria_id):
    """Активация/деактивация критерия"""
    criteria = get_object_or_404(CommentModerationCriteria, id=criteria_id)
    criteria.is_active = not criteria.is_active
    criteria.save()
    
    action = 'активирован' if criteria.is_active else 'деактивирован'
    messages.success(request, f'Критерий "{criteria.name}" {action}!')
    return redirect('moderation:comment_list')


@login_required
@user_passes_test(is_moderator)
def comment_criteria_delete(request, criteria_id):
    """Удаление критерия"""
    criteria = get_object_or_404(CommentModerationCriteria, id=criteria_id)
    
    if request.method == 'POST':
        name = criteria.name
        criteria.delete()
        messages.success(request, f'Критерий "{name}" успешно удален!')
        return redirect('moderation:comment_list')
    
    # Подсчет использования
    usage_count = CommentModeration.objects.filter(criteria_used=criteria).count()
    
    context = {
        'criteria': criteria,
        'usage_count': usage_count,
    }
    return render(request, 'moderation/comment_criteria_delete.html', context)


@login_required
@user_passes_test(is_moderator)
def article_create(request):
    """Ручное создание новой статьи из панели модерации."""
    if request.method == 'POST':
        form = PostEditForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            # slug генерируется автоматически моделью если пустой
            post.save()
            form.save_m2m()  # теги
            # Создаём запись модерации
            ArticleModeration.objects.create(
                post=post,
                submitted_at=timezone.now(),
                status='pending',
            )
            messages.success(request, f'Статья «{post.title}» создана.')
            return redirect('moderation:article_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = PostEditForm()

    return render(request, 'moderation/article_create.html', {
        'form': form,
        'title': 'Создание новой статьи',
    })
