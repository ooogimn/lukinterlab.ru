"""
Views для дашборда управления автопостингом
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from datetime import timedelta
import json

from .models import PromptTemplate, AISchedule, AIGeneratedArticle, AssistantSettings, TokenUsage
from .token_cost_analysis import TokenCostAnalyzer
from . import forms
from .tasks import run_schedule_task
from .article_generator import ArticleGeneratorService
from django_q.tasks import async_task
from django_q.models import Schedule as QSchedule

logger = __import__('logging').getLogger(__name__)


"""Проверка, что пользователь суперюзер"""
def is_superuser(user):
    """Проверка, что пользователь суперюзер"""
    return user.is_authenticated and user.is_superuser


"""Главная страница дашборда с общей статистикой"""
@login_required
@user_passes_test(is_superuser)
def dashboard_main(request):
    """Главная страница дашборда с общей статистикой"""
    
    # Статистика шаблонов
    templates_count = PromptTemplate.objects.count()
    active_templates = PromptTemplate.objects.filter(is_active=True).count()
    
    # Статистика расписаний
    schedules_count = AISchedule.objects.count()
    active_schedules = AISchedule.objects.filter(is_active=True).count()
    
    # Статистика генерации
    total_generated = AIGeneratedArticle.objects.count()
    today_generated = AIGeneratedArticle.objects.filter(
        created_at__date=timezone.now().date()
    ).count()
    week_generated = AIGeneratedArticle.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    # Статистика по расписаниям
    schedules_stats = AISchedule.objects.annotate(
        articles_count=Count('generated_articles')
    ).order_by('-total_generated')[:5]
    
    # Последние сгенерированные статьи
    recent_articles = AIGeneratedArticle.objects.select_related(
        'post', 'schedule', 'prompt_template'
    ).order_by('-created_at')[:10]
    
    # Статистика по времени генерации
    avg_generation_time = AIGeneratedArticle.objects.filter(
        generation_time__isnull=False
    ).aggregate(avg_time=Avg('generation_time'))['avg_time'] or 0
    
    # Статистика по токенам (за последние 30 дней)
    token_stats = TokenUsage.get_statistics(days=30)
    total_tokens_30d = token_stats['total'].get('total_tokens', 0) or 0
    total_cost_30d = token_stats['total'].get('total_cost', 0) or 0
    
    # Получаем реальный баланс из API GigaChat
    token_limits_status = []
    try:
        settings = AssistantSettings.objects.first()
        if settings:
            from .ai_service import GigaChatAPIService
            gigachat_service = GigaChatAPIService(settings)
            api_balance = gigachat_service.get_balance()
            
            # Список моделей для отображения (актуальные модели GigaChat 2)
            models_to_check = [
                'GigaChat-2-Lite',
                'GigaChat-2-Pro', 
                'GigaChat-2-Max',
                'Embeddings'
            ]
            
            if api_balance and 'data' in api_balance:
                # API вернул баланс - используем реальные данные
                balance_by_model = {}
                for balance_item in api_balance.get('data', []):
                    model_name = balance_item.get('model', '')
                    balance = balance_item.get('balance', 0)
                    balance_by_model[model_name] = balance
                    logger.debug(f"API баланс для {model_name}: {balance} токенов")
                
                # Получаем использованные токены из БД за последние 30 дней
                used_by_model = {}
                for model_stat in token_stats.get('by_model', []):
                    model_name = model_stat.get('model', '')
                    used_tokens = model_stat.get('tokens', 0) or 0
                    used_by_model[model_name] = used_tokens
                
                # Формируем статус для каждой модели
                for model_name in models_to_check:
                    # Ищем баланс в API ответе (может быть с префиксом или без)
                    api_balance_value = None
                    matched_api_model = None
                    for api_model, balance in balance_by_model.items():
                        # Сопоставляем модели (GigaChat-2-Lite может быть как "GigaChat-2-Lite" или "GigaChat-Lite")
                        if model_name in api_model or api_model in model_name:
                            api_balance_value = balance
                            matched_api_model = api_model
                            break
                    
                    # Если не нашли точное совпадение, пробуем варианты
                    if api_balance_value is None:
                        # Варианты названий моделей
                        model_variants = {
                            'GigaChat-2-Lite': ['GigaChat-2-Lite', 'GigaChat-Lite', 'GigaChat'],
                            'GigaChat-2-Pro': ['GigaChat-2-Pro', 'GigaChat-Pro'],
                            'GigaChat-2-Max': ['GigaChat-2-Max', 'GigaChat-Max'],
                            'Embeddings': ['Embeddings', 'EmbeddingsGigaR'],
                        }
                        for variant in model_variants.get(model_name, [model_name]):
                            if variant in balance_by_model:
                                api_balance_value = balance_by_model[variant]
                                matched_api_model = variant
                                break
                    
                    # Использованные токены из БД
                    used_tokens = used_by_model.get(model_name, 0)
                    # Пробуем найти использованные токены по вариантам названий
                    if used_tokens == 0:
                        for variant in [model_name, model_name.replace('GigaChat-2-', 'GigaChat-')]:
                            if variant in used_by_model:
                                used_tokens = used_by_model[variant]
                                logger.debug(f"Найдены использованные токены для {model_name} через вариант {variant}: {used_tokens}")
                                break
                    
                    # Лимит из модели (fallback если API не вернул баланс)
                    # Используем метод get_limit_for_model для получения лимита с учетом подписки
                    fallback_limit = TokenUsage.get_limit_for_model(model_name)
                    
                    if api_balance_value is not None:
                        # API вернул остаток токенов (balance) - это остаток, а не лимит!
                        remaining = api_balance_value
                        
                        # ВАЖНО: API возвращает только остаток токенов, а не общий лимит
                        # Если у нас есть остаток и использованные токены за период, мы можем оценить лимит
                        # Но правильнее использовать fallback лимит как базовый, а остаток из API как актуальный
                        
                        # Используем fallback лимит как базовый, но если остаток + использовано > fallback,
                        # значит лимит больше (возможно, куплен больший пакет)
                        estimated_limit = max(fallback_limit, remaining + used_tokens)
                        
                        # Если остаток близок к fallback лимиту, используем fallback
                        # Если остаток значительно больше, значит лимит больше
                        if remaining >= fallback_limit * 0.9:
                            # Остаток близок к fallback - используем fallback как лимит
                            total_limit = fallback_limit
                        else:
                            # Остаток меньше - возможно, использованы токены
                            # Используем максимальное значение: fallback или (остаток + использовано)
                            total_limit = estimated_limit
                        
                        # Процент использования: использовано / лимит
                        used_percent = (used_tokens / total_limit * 100) if total_limit > 0 else 0
                        
                        logger.debug(f"Модель {model_name}: остаток={remaining}, использовано={used_tokens}, лимит={total_limit}, %={used_percent:.1f}")
                    else:
                        # Fallback на статический лимит (API не вернул данные для этой модели)
                        remaining = max(0, fallback_limit - used_tokens)
                        total_limit = fallback_limit
                        used_percent = (used_tokens / total_limit * 100) if total_limit > 0 else 0
                        logger.debug(f"Модель {model_name}: fallback, остаток={remaining}, использовано={used_tokens}, лимит={total_limit}")
                    
                    token_limits_status.append({
                        'model': model_name,
                        'limit': total_limit,
                        'used': used_tokens,
                        'remaining': remaining,
                        'used_percent': used_percent,
                        'is_near_limit': used_percent > 80 or remaining < total_limit * 0.2,
                        'is_critical': used_percent > 95 or remaining < total_limit * 0.05,
                        'from_api': api_balance_value is not None,  # Флаг: данные из API или fallback
                    })
            else:
                # API не вернул баланс (403 или ошибка) - используем fallback на локальные данные
                logger.warning("API баланс недоступен, используем локальные данные из БД")
                for model_name in models_to_check:
                    try:
                        limit_info = TokenUsage.check_limits(model_name)
                        limit_info['from_api'] = False  # Флаг: данные не из API
                        token_limits_status.append(limit_info)
                    except Exception as e:
                        logger.warning(f"Ошибка проверки лимитов для {model_name}: {str(e)}")
        else:
            # Настройки не найдены - используем fallback
            for model_name in models_to_check:
                try:
                    limit_info = TokenUsage.check_limits(model_name)
                    limit_info['from_api'] = False
                    token_limits_status.append(limit_info)
                except Exception as e:
                    logger.warning(f"Ошибка проверки лимитов для {model_name}: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка получения баланса из API: {str(e)}")
        # Fallback на локальные данные
        for model_name in ['GigaChat-2-Lite', 'GigaChat-2-Pro', 'GigaChat-2-Max', 'Embeddings']:
            try:
                limit_info = TokenUsage.check_limits(model_name)
                limit_info['from_api'] = False
                token_limits_status.append(limit_info)
            except Exception as e2:
                logger.warning(f"Ошибка проверки лимитов для {model_name}: {str(e2)}")
    
    # Анализ стоимости (если бы использовалась пакетная оплата)
    try:
        cost_analysis = TokenCostAnalyzer.calculate_potential_cost(days=30)
        efficiency_report = TokenCostAnalyzer.get_cost_efficiency_report(days=30)
    except Exception as e:
        logger.warning(f"Ошибка анализа стоимости токенов: {str(e)}")
        cost_analysis = None
        efficiency_report = None
    
    # Статистика по расписаниям Django-Q
    q_schedules = QSchedule.objects.filter(
        func='Assistant.tasks.run_schedule_task'
    ).count()
    
    # Проверка настроек GigaChat
    gigachat_configured = False
    try:
        settings = AssistantSettings.objects.first()
        if settings:
            # Если провайдер установлен как GigaChat, считаем что настроено
            if settings.ai_provider == 'gigachat':
                gigachat_configured = True
            else:
                # Проверяем новый способ (Authorization Key)
                try:
                    auth_key = settings.get_gigachat_authorization_key()
                    if auth_key and auth_key.strip():
                        gigachat_configured = True
                except:
                    pass
                
                # Проверяем старый способ (Client ID + Secret) для обратной совместимости
                if not gigachat_configured:
                    client_id = settings.gigachat_client_id
                    try:
                        client_secret = settings.get_gigachat_client_secret()
                        if client_id and client_secret:
                            gigachat_configured = True
                    except:
                        pass
                
                # Также проверяем, что поле не пустое в базе (даже если зашифровано)
                if not gigachat_configured and settings.gigachat_authorization_key:
                    gigachat_configured = True
    except Exception as e:
        logger.error(f"Ошибка проверки настроек GigaChat: {str(e)}")
        # Если есть настройки, считаем что настроено
        try:
            if AssistantSettings.objects.exists():
                gigachat_configured = True
        except:
            pass
    
    context = {
        'templates_count': templates_count,
        'active_templates': active_templates,
        'schedules_count': schedules_count,
        'active_schedules': active_schedules,
        'total_generated': total_generated,
        'today_generated': today_generated,
        'week_generated': week_generated,
        'schedules_stats': schedules_stats,
        'recent_articles': recent_articles,
        'avg_generation_time': round(avg_generation_time, 2),
        'q_schedules': q_schedules,
        'gigachat_configured': gigachat_configured,
        'total_tokens_30d': total_tokens_30d,
        'total_cost_30d': float(total_cost_30d),
        'token_stats_by_model': token_stats.get('by_model', []),
        'token_limits_status': token_limits_status,  # Лимиты токенов для главной страницы
        'cost_analysis': cost_analysis,
        'efficiency_report': efficiency_report,
    }
    
    return render(request, 'assistant/dashboard/main.html', context)


"""Список шаблонов промптов"""
@login_required
@user_passes_test(is_superuser)
def templates_list(request):
    """Список шаблонов промптов"""
    templates = PromptTemplate.objects.all().order_by('-created_at')
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        templates = templates.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Фильтр по активности
    active_filter = request.GET.get('active', '')
    if active_filter == 'true':
        templates = templates.filter(is_active=True)
    elif active_filter == 'false':
        templates = templates.filter(is_active=False)
    
    # Пагинация
    paginator = Paginator(templates, 20)
    page = request.GET.get('page', 1)
    templates_page = paginator.get_page(page)
    
    context = {
        'templates': templates_page,
        'search_query': search_query,
        'active_filter': active_filter,
    }
    
    return render(request, 'assistant/dashboard/templates_list.html', context)


"""Создание нового шаблона промпта"""
@login_required
@user_passes_test(is_superuser)
def template_create(request):
    """Создание нового шаблона промпта"""
    if request.method == 'POST':
        form = forms.PromptTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            template.save()
            messages.success(request, f'Шаблон "{template.name}" успешно создан!')
            return redirect('assistant:dashboard_templates')
        else:
            messages.error(request, 'Ошибка при создании шаблона. Проверьте форму.')
    else:
        form = forms.PromptTemplateForm()
    
    return render(request, 'assistant/dashboard/template_form.html', {
        'form': form,
        'title': 'Создать шаблон промпта'
    })


"""Редактирование шаблона промпта"""
@login_required
@user_passes_test(is_superuser)
def template_edit(request, pk):
    """Редактирование шаблона промпта"""
    template = get_object_or_404(PromptTemplate, pk=pk)
    
    if request.method == 'POST':
        logger.info(f"[TEMPLATE_EDIT] Получен POST запрос для шаблона {pk}")
        form = forms.PromptTemplateForm(request.POST, request.FILES, instance=template)
        
        if form.is_valid():
            logger.info(f"[TEMPLATE_EDIT] Форма валидна, сохраняем шаблон {pk}")
            template = form.save()
            logger.info(f"[TEMPLATE_EDIT] Шаблон {pk} успешно сохранён: {template.name}")
            messages.success(request, f'Шаблон "{template.name}" успешно обновлён!')
            return redirect('assistant:dashboard_templates')
        else:
            logger.warning(f"[TEMPLATE_EDIT] Ошибки валидации формы шаблона {pk}: {form.errors}")
            messages.error(request, 'Ошибка при сохранении шаблона. Проверьте форму.')
            # Выводим ошибки в консоль для отладки
            for field, errors in form.errors.items():
                for error in errors:
                    logger.warning(f"[TEMPLATE_EDIT] Поле '{field}': {error}")
    else:
        form = forms.PromptTemplateForm(instance=template)
    
    return render(request, 'assistant/dashboard/template_form.html', {
        'form': form,
        'template': template,
        'title': 'Редактировать шаблон промпта'
    })


"""Удаление шаблона промпта"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def template_delete(request, pk):
    """Удаление шаблона промпта"""
    template = get_object_or_404(PromptTemplate, pk=pk)
    
    # Проверяем, используется ли шаблон в расписаниях
    if AISchedule.objects.filter(prompt_template=template).exists():
        return JsonResponse({
            'success': False,
            'error': 'Шаблон используется в расписаниях. Сначала удалите расписания.'
        })
    
    template.delete()
    return JsonResponse({'success': True})


"""Список расписаний"""
@login_required
@user_passes_test(is_superuser)
def schedules_list(request):
    """Список расписаний"""
    schedules = AISchedule.objects.select_related(
        'prompt_template', 'category', 'created_by'
    ).annotate(
        articles_count=Count('generated_articles')
    ).order_by('-created_at')
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        schedules = schedules.filter(
            Q(name__icontains=search_query) |
            Q(keywords__icontains=search_query)
        )
    
    # Фильтр по активности
    active_filter = request.GET.get('active', '')
    if active_filter == 'true':
        schedules = schedules.filter(is_active=True)
    elif active_filter == 'false':
        schedules = schedules.filter(is_active=False)
    
    # Пагинация
    paginator = Paginator(schedules, 20)
    page = request.GET.get('page', 1)
    schedules_page = paginator.get_page(page)
    
    context = {
        'schedules': schedules_page,
        'search_query': search_query,
        'active_filter': active_filter,
    }
    
    return render(request, 'assistant/dashboard/schedules_list.html', context)


"""Создание нового расписания"""
@login_required
@user_passes_test(is_superuser)
def schedule_create(request):
    """Создание нового расписания"""
    if request.method == 'POST':
        form = forms.AIScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.created_by = request.user
            schedule.save()
            
            # Настраиваем расписание в Django-Q
            from .tasks import setup_schedules
            setup_schedules()
            
            return redirect('assistant:dashboard_schedules')
    else:
        form = forms.AIScheduleForm()
    
    return render(request, 'assistant/dashboard/schedule_form.html', {
        'form': form,
        'title': 'Создать расписание'
    })


"""Редактирование расписания"""
@login_required
@user_passes_test(is_superuser)
def schedule_edit(request, pk):
    """Редактирование расписания"""
    schedule = get_object_or_404(AISchedule, pk=pk)
    
    if request.method == 'POST':
        form = forms.AIScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            schedule = form.save()
            
            # Обновляем расписание в Django-Q
            from .tasks import setup_schedules
            setup_schedules()
            
            return redirect('assistant:dashboard_schedules')
    else:
        form = forms.AIScheduleForm(instance=schedule)
    
    return render(request, 'assistant/dashboard/schedule_form.html', {
        'form': form,
        'schedule': schedule,
        'title': 'Редактировать расписание'
    })


"""Удаление расписания"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def schedule_delete(request, pk):
    """Удаление расписания"""
    schedule = get_object_or_404(AISchedule, pk=pk)
    
    # Удаляем расписание из Django-Q
    from .tasks import remove_schedule
    remove_schedule(schedule.id)
    
    schedule.delete()
    return JsonResponse({'success': True})


"""Ручной запуск генерации по расписанию"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def schedule_run_now(request, pk):
    """Ручной запуск генерации по расписанию"""
    schedule = get_object_or_404(AISchedule, pk=pk)
    
    try:
        # Запускаем задачу асинхронно
        async_task('Assistant.tasks.run_schedule_task', schedule.id)
        return JsonResponse({
            'success': True,
            'message': f'Генерация для расписания "{schedule.name}" запущена'
        })
    except Exception as e:
        logger.error(f"Ошибка запуска генерации: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


"""История генерации статей"""
@login_required
@user_passes_test(is_superuser)
def history_list(request):
    """История генерации статей"""
    articles = AIGeneratedArticle.objects.select_related(
        'post', 'schedule', 'prompt_template'
    ).order_by('-created_at')
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        articles = articles.filter(
            Q(post__title__icontains=search_query) |
            Q(generated_title__icontains=search_query)
        )
    
    # Фильтр по расписанию
    schedule_filter = request.GET.get('schedule', '')
    if schedule_filter:
        articles = articles.filter(schedule_id=schedule_filter)
    
    # Фильтр по дате
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        articles = articles.filter(created_at__gte=date_from)
    if date_to:
        articles = articles.filter(created_at__lte=date_to)
    
    # Пагинация
    paginator = Paginator(articles, 20)
    page = request.GET.get('page', 1)
    articles_page = paginator.get_page(page)
    
    # Список расписаний для фильтра
    schedules = AISchedule.objects.all().order_by('name')
    
    context = {
        'articles': articles_page,
        'search_query': search_query,
        'schedule_filter': schedule_filter,
        'date_from': date_from,
        'date_to': date_to,
        'schedules': schedules,
    }
    
    return render(request, 'assistant/dashboard/history_list.html', context)


"""Очистка истории генерации статей"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def history_clear(request):
    """Очистка всей истории генерации статей"""
    try:
        count = AIGeneratedArticle.objects.all().count()
        AIGeneratedArticle.objects.all().delete()
        logger.info(f"[HISTORY] Очищена история генерации: удалено {count} записей")
        messages.success(request, f'История очищена. Удалено записей: {count}')
        return redirect('assistant:dashboard_history')
    except Exception as e:
        logger.error(f"[ERROR] Ошибка очистки истории: {str(e)}", exc_info=True)
        messages.error(request, f'Ошибка очистки истории: {str(e)}')
        return redirect('assistant:dashboard_history')


"""Удаление выбранных статей из истории"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def history_delete_selected(request):
    """Удаление выбранных статей из истории"""
    try:
        selected_ids = request.POST.getlist('selected_articles')
        if not selected_ids:
            messages.warning(request, 'Не выбрано ни одной статьи для удаления')
            return redirect('assistant:dashboard_history')
        
        # Преобразуем в список целых чисел и удаляем
        article_ids = []
        for id_str in selected_ids:
            try:
                article_ids.append(int(id_str))
            except (ValueError, TypeError):
                continue
        
        if not article_ids:
            messages.error(request, 'Неверный формат выбранных статей')
            return redirect('assistant:dashboard_history')
        
        # Удаляем выбранные статьи
        deleted_count = AIGeneratedArticle.objects.filter(pk__in=article_ids).delete()[0]
        logger.info(f"[HISTORY] Удалено выбранных статей: {deleted_count} записей (IDs: {article_ids})")
        messages.success(request, f'Удалено статей: {deleted_count}')
        
        # Сохраняем параметры фильтрации при редиректе
        redirect_url = reverse('assistant:dashboard_history')
        query_params = request.GET.urlencode()
        if query_params:
            redirect_url = f"{redirect_url}?{query_params}"
        return HttpResponseRedirect(redirect_url)
    except Exception as e:
        logger.error(f"[ERROR] Ошибка удаления выбранных статей: {str(e)}", exc_info=True)
        messages.error(request, f'Ошибка удаления выбранных статей: {str(e)}')
        redirect_url = reverse('assistant:dashboard_history')
        query_params = request.GET.urlencode()
        if query_params:
            redirect_url = f"{redirect_url}?{query_params}"
        return HttpResponseRedirect(redirect_url)


"""Детальная информация о сгенерированной статье"""
@login_required
@user_passes_test(is_superuser)
def history_detail(request, pk):
    """Детальная информация о сгенерированной статье"""
    article = get_object_or_404(AIGeneratedArticle, pk=pk)
    
    return render(request, 'assistant/dashboard/history_detail.html', {
        'article': article
    })


"""Мониторинг системы автопостинга"""
@login_required
@user_passes_test(is_superuser)
def monitoring(request):
    """Мониторинг системы автопостинга"""
    
    # Статус GigaChat
    gigachat_status = {
        'configured': False,
        'model': None,
        'scope': None,
    }
    try:
        settings = AssistantSettings.objects.first()
        if settings:
            # Если провайдер установлен как GigaChat, считаем что настроено
            if settings.ai_provider == 'gigachat':
                gigachat_status['configured'] = True
            else:
                # Проверяем новый способ (Authorization Key)
                try:
                    auth_key = settings.get_gigachat_authorization_key()
                    if auth_key and auth_key.strip():
                        gigachat_status['configured'] = True
                except:
                    pass
                
                # Проверяем старый способ (Client ID + Secret) для обратной совместимости
                if not gigachat_status['configured']:
                    client_id = settings.gigachat_client_id
                    try:
                        client_secret = settings.get_gigachat_client_secret()
                        if client_id and client_secret:
                            gigachat_status['configured'] = True
                    except:
                        pass
                
                # Также проверяем, что поле не пустое в базе (даже если зашифровано)
                if not gigachat_status['configured'] and settings.gigachat_authorization_key:
                    gigachat_status['configured'] = True
            
            gigachat_status['model'] = settings.ai_model
            gigachat_status['scope'] = settings.gigachat_scope
    except Exception as e:
        logger.error(f"Ошибка проверки статуса GigaChat: {str(e)}")
        # Если есть настройки, считаем что настроено
        try:
            if AssistantSettings.objects.exists():
                gigachat_status['configured'] = True
        except:
            pass
    
    # Статус расписаний Django-Q
    q_schedules = QSchedule.objects.filter(
        func='Assistant.tasks.run_schedule_task'
    )
    
    q_schedules_status = []
    for q_schedule in q_schedules:
        # Извлекаем schedule_id из args
        try:
            schedule_id = int(q_schedule.args) if q_schedule.args else None
            if schedule_id:
                ai_schedule = AISchedule.objects.filter(id=schedule_id).first()
                q_schedules_status.append({
                    'q_schedule': q_schedule,
                    'ai_schedule': ai_schedule,
                    'next_run': q_schedule.next_run,
                    'last_run': q_schedule.last_run,
                })
        except:
            pass
    
    # Статистика за последние 24 часа
    last_24h = timezone.now() - timedelta(hours=24)
    stats_24h = {
        'generated': AIGeneratedArticle.objects.filter(created_at__gte=last_24h).count(),
        'avg_time': AIGeneratedArticle.objects.filter(
            created_at__gte=last_24h,
            generation_time__isnull=False
        ).aggregate(avg=Avg('generation_time'))['avg'] or 0,
        'success_rate': 100,  # TODO: рассчитать на основе ошибок
    }
    
    # Последние ошибки (если есть логирование ошибок)
    # TODO: добавить модель для хранения ошибок
    
    # Проверка лимитов токенов (используем реальный API баланс)
    token_limits_status = []
    try:
        settings = AssistantSettings.objects.first()
        if settings:
            from .ai_service import GigaChatAPIService
            gigachat_service = GigaChatAPIService(settings)
            api_balance = gigachat_service.get_balance()
            
            models_to_check = ['GigaChat-2-Lite', 'GigaChat-2-Pro', 'GigaChat-2-Max', 'Embeddings']
            
            if api_balance and 'data' in api_balance:
                # Используем реальный API баланс (логика аналогична dashboard_main)
                balance_by_model = {}
                for balance_item in api_balance.get('data', []):
                    model_name = balance_item.get('model', '')
                    balance = balance_item.get('balance', 0)
                    balance_by_model[model_name] = balance
                    logger.debug(f"[monitoring] API баланс для {model_name}: {balance} токенов")
                
                stats = TokenUsage.get_statistics(days=30)
                used_by_model = {m.get('model', ''): m.get('tokens', 0) or 0 for m in stats.get('by_model', [])}
                
                for model_name in models_to_check:
                    api_balance_value = None
                    matched_api_model = None
                    for api_model, balance in balance_by_model.items():
                        if model_name in api_model or api_model in model_name:
                            api_balance_value = balance
                            matched_api_model = api_model
                            break
                    
                    # Если не нашли точное совпадение, пробуем варианты
                    if api_balance_value is None:
                        model_variants = {
                            'GigaChat-2-Lite': ['GigaChat-2-Lite', 'GigaChat-Lite', 'GigaChat'],
                            'GigaChat-2-Pro': ['GigaChat-2-Pro', 'GigaChat-Pro'],
                            'GigaChat-2-Max': ['GigaChat-2-Max', 'GigaChat-Max'],
                            'Embeddings': ['Embeddings', 'EmbeddingsGigaR'],
                        }
                        for variant in model_variants.get(model_name, [model_name]):
                            if variant in balance_by_model:
                                api_balance_value = balance_by_model[variant]
                                matched_api_model = variant
                                break
                    
                    used_tokens = used_by_model.get(model_name, 0)
                    # Пробуем найти использованные токены по вариантам названий
                    if used_tokens == 0:
                        for variant in [model_name, model_name.replace('GigaChat-2-', 'GigaChat-')]:
                            if variant in used_by_model:
                                used_tokens = used_by_model[variant]
                                break
                    
                    fallback_limit = TokenUsage.get_limit_for_model(model_name)
                    
                    if api_balance_value is not None:
                        # API вернул остаток токенов (balance)
                        remaining = api_balance_value
                        
                        # Используем fallback лимит как базовый, но если остаток + использовано > fallback,
                        # значит лимит больше (возможно, куплен больший пакет)
                        estimated_limit = max(fallback_limit, remaining + used_tokens)
                        
                        # Если остаток близок к fallback лимиту, используем fallback
                        if remaining >= fallback_limit * 0.9:
                            total_limit = fallback_limit
                        else:
                            total_limit = estimated_limit
                        
                        used_percent = (used_tokens / total_limit * 100) if total_limit > 0 else 0
                    else:
                        remaining = max(0, fallback_limit - used_tokens)
                        total_limit = fallback_limit
                        used_percent = (used_tokens / total_limit * 100) if total_limit > 0 else 0
                    
                    token_limits_status.append({
                        'model': model_name,
                        'limit': total_limit,
                        'used': used_tokens,
                        'remaining': remaining,
                        'used_percent': used_percent,
                        'is_near_limit': used_percent > 80 or remaining < total_limit * 0.2,
                        'is_critical': used_percent > 95 or remaining < total_limit * 0.05,
                        'from_api': api_balance_value is not None,
                    })
            else:
                # Fallback на локальные данные
                for model_name in models_to_check:
                    try:
                        limit_info = TokenUsage.check_limits(model_name)
                        token_limits_status.append(limit_info)
                    except:
                        pass
        else:
            # Fallback если настройки не найдены
            for model_name in models_to_check:
                try:
                    limit_info = TokenUsage.check_limits(model_name)
                    token_limits_status.append(limit_info)
                except:
                    pass
    except Exception as e:
        logger.error(f"Ошибка получения баланса в monitoring: {str(e)}")
        # Fallback
        for model_name in ['GigaChat-2-Lite', 'GigaChat-2-Pro', 'GigaChat-2-Max', 'Embeddings']:
            try:
                limit_info = TokenUsage.check_limits(model_name)
                token_limits_status.append(limit_info)
            except:
                pass
    
    # Статистика токенов для графиков (последние 7 дней)
    daily_token_stats = TokenUsage.get_daily_stats(days=7) if hasattr(TokenUsage, 'get_daily_stats') else []
    
    context = {
        'gigachat_status': gigachat_status,
        'q_schedules_status': q_schedules_status,
        'stats_24h': stats_24h,
        'token_limits_status': token_limits_status,
        'daily_token_stats': list(daily_token_stats),
    }
    
    return render(request, 'assistant/dashboard/monitoring.html', context)


"""API для получения статистики (AJAX)"""
@login_required
@user_passes_test(is_superuser)
def api_statistics(request):
    """API для получения статистики (AJAX)"""
    stats = {
        'templates': {
            'total': PromptTemplate.objects.count(),
            'active': PromptTemplate.objects.filter(is_active=True).count(),
        },
        'schedules': {
            'total': AISchedule.objects.count(),
            'active': AISchedule.objects.filter(is_active=True).count(),
        },
        'generated': {
            'total': AIGeneratedArticle.objects.count(),
            'today': AIGeneratedArticle.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'week': AIGeneratedArticle.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
        },
        'avg_generation_time': AIGeneratedArticle.objects.filter(
            generation_time__isnull=False
        ).aggregate(avg=Avg('generation_time'))['avg'] or 0,
    }
    
    return JsonResponse(stats)


"""Страница тестирования шаблона промпта"""
@login_required
@user_passes_test(is_superuser)
def template_test(request, pk):
    """
    Полноценная страница тестирования шаблона промпта с действиями
    Адаптировано под структуру с раздельными промптами (title_prompt, content_prompt, image_prompt, additional_section_prompt)
    """
    from Blog.models import Post, Category
    from django.contrib import messages
    template = get_object_or_404(PromptTemplate, pk=pk)
    
    test_result = None
    test_variables = {}
    test_post = None
    
    # Получаем категории для выбора
    categories = Category.objects.filter(activ=True).order_by('title')
    
    # Получаем последнюю тестовую статью (если есть)
    if request.GET.get('post_id'):
        try:
            test_post = Post.objects.get(
                pk=request.GET.get('post_id'), 
                author__username='ai_assistant'
            )
        except Post.DoesNotExist:
            pass
    
    # Обработка POST запросов (действия с тестовой статьёй)
    if request.method == 'POST':
        action = request.POST.get('action', 'test')
        
        # ДЕЙСТВИЯ С ТЕСТОВОЙ СТАТЬЁЙ
        if action == 'publish':
            post_id = request.POST.get('post_id')
            if post_id:
                try:
                    post = Post.objects.get(pk=post_id, author__username='ai_assistant')
                    # Убираем маркер тестовой статьи из description
                    if post.description and '[TEST_ARTICLE]' in post.description:
                        post.description = post.description.replace('[TEST_ARTICLE]', '').strip()
                    post.status = 'published'
                    post.save(update_fields=['status', 'description'])
                    messages.success(request, f'Статья "{post.title}" опубликована')
                    return redirect('assistant:dashboard_template_test', pk=pk)
                except Post.DoesNotExist:
                    messages.error(request, 'Статья не найдена')
        
        elif action == 'draft':
            post_id = request.POST.get('post_id')
            if post_id:
                try:
                    post = Post.objects.get(pk=post_id, author__username='ai_assistant')
                    post.status = 'draft'
                    post.save(update_fields=['status'])
                    messages.success(request, f'Статья "{post.title}" переведена в черновик')
                    return redirect('assistant:dashboard_template_test', pk=pk)
                except Post.DoesNotExist:
                    messages.error(request, 'Статья не найдена')
        
        elif action == 'delete':
            post_id = request.POST.get('post_id')
            if post_id:
                try:
                    post = Post.objects.get(pk=post_id, author__username='ai_assistant')
                    post_title = post.title
                    post.delete()
                    messages.success(request, f'Статья "{post_title}" удалена')
                    return redirect('assistant:dashboard_template_test', pk=pk)
                except Post.DoesNotExist:
                    messages.error(request, 'Статья не найдена')
        
        elif action == 'queue':
            # Создание расписания из тестовой статьи
            post_id = request.POST.get('post_id')
            if post_id:
                try:
                    post = Post.objects.get(pk=post_id, author__username='ai_assistant')
                    # Редирект на страницу создания расписания с предзаполненными данными
                    return redirect('assistant:dashboard_schedule_create', post_id=post_id)
                except Post.DoesNotExist:
                    messages.error(request, 'Статья не найдена')
        
        # ЗАПУСК ТЕСТА - ПОЛНАЯ ГЕНЕРАЦИЯ СТАТЬИ
        elif action == 'test':
            try:
                # Собираем переменные из формы
                test_variables = {}
                
                # Получаем все переменные из шаблона
                variables_dict = template.extract_variables(include_system=True)
                all_variables = variables_dict.get('all', [])
                
                # Собираем значения переменных из POST
                for var_name in all_variables:
                    value = request.POST.get(f'var_{var_name}', '').strip()
                    if value:
                        test_variables[var_name] = value
                
                # Получаем категорию
                category_id = request.POST.get('category_id')
                if category_id:
                    try:
                        category = Category.objects.get(pk=category_id, activ=True)
                    except Category.DoesNotExist:
                        category = template.default_category
                else:
                    category = template.default_category
                
                if not category:
                    try:
                        category = Category.objects.get(slug='vysoko-intellektualnye-novosti')
                    except Category.DoesNotExist:
                        test_result = {
                            'success': False,
                            'error': 'Категория не найдена. Укажите категорию в шаблоне или создайте категорию "vysoko-intellektualnye-novosti"'
                        }
                        return render(request, 'assistant/dashboard/template_test.html', {
                            'template': template,
                            'categories': categories,
                            'test_variables': test_variables,
                            'test_result': test_result,
                            'test_post': None,
                        })
                
                # Получаем ключевые слова
                keywords = request.POST.get('keywords', '').strip()
                
                # Объединяем переменные
                # Базовые системные переменные
                full_context = {
                    'category': category.title,
                    'keywords': keywords,
                }
                
                # Затем добавляем пользовательские переменные из формы (переопределяют системные)
                full_context.update(test_variables)
                
                logger.info(f"[TEMPLATE_TEST] Контекст для генерации: {list(full_context.keys())}")
                
                # Создаем сервис генерации для тестирования
                generator = ArticleGeneratorService(prompt_template=template)
                
                # Генерируем статью с полным контекстом
                post = generator.generate_test_article(
                    category=category,
                    keywords=keywords,
                    context_data=full_context
                )
                
                if not post:
                    test_result = {
                        'success': False,
                        'error': 'Не удалось сгенерировать статью. Проверьте логи.'
                    }
                else:
                    # Добавляем маркер тестовой статьи в description
                    if post.description:
                        post.description = f'[TEST_ARTICLE] {post.description}'
                    else:
                        post.description = '[TEST_ARTICLE]'
                    post.save(update_fields=['description'])
                    
                    test_result = {
                        'success': True,
                        'post_id': post.id,
                        'title': post.title,
                        'status': post.status,
                        'description': post.description.replace('[TEST_ARTICLE]', '').strip() if post.description else '',
                        'image_url': post.kartinka.url if post.kartinka else None,
                        'category': post.category.title if post.category else '',
                        'created': post.created.isoformat() if post.created else '',
                        'content_preview': post.content[:500] if post.content else '',
                        'word_count': len(post.content.split()) if post.content else 0,
                    }
                    test_post = post
                    
            except Exception as e:
                logger.error(f"Ошибка тестирования шаблона {pk}: {str(e)}", exc_info=True)
                test_result = {
                    'success': False,
                    'error': f'Ошибка тестирования: {str(e)}'
                }
    
    # Подготовка переменных для отображения
    variables_dict = template.extract_variables(include_system=True)
    default_vars = {}
    
    # Заполняем значения по умолчанию для системных переменных
    if variables_dict.get('system'):
        for var_name in variables_dict['system']:
            if var_name == 'category' and template.default_category:
                default_vars[var_name] = template.default_category.title
            elif var_name == 'keywords':
                default_vars[var_name] = ''
            elif var_name == 'topic':
                default_vars[var_name] = ''
            else:
                default_vars[var_name] = ''
    
    return render(request, 'assistant/dashboard/template_test.html', {
        'template': template,
        'categories': categories,
        'default_vars': default_vars,
        'test_variables': test_variables,
        'test_result': test_result,
        'test_post': test_post,
        'title': f'Тест: {template.name}',
    })


"""AJAX получение списка динамических переменных из шаблона"""
@login_required
@user_passes_test(is_superuser)
def template_test_variables(request, pk):
    """
    API: Получить список переменных из шаблона промпта для автоподгрузки
    Адаптировано под структуру с раздельными промптами
    """
    template = get_object_or_404(PromptTemplate, pk=pk)
    
    try:
        # Используем метод extract_variables из модели
        variables_dict = template.extract_variables(include_system=True)
        
        all_vars = variables_dict.get('all', [])
        system_vars = variables_dict.get('system', [])
        custom_vars = variables_dict.get('custom', [])
        
        logger.info(f"[TEMPLATE_VARIABLES] Шаблон {pk}: найдено {len(all_vars)} переменных "
                   f"({len(system_vars)} системных, {len(custom_vars)} пользовательских)")
        logger.info(f"[TEMPLATE_VARIABLES] Системные: {system_vars}")
        logger.info(f"[TEMPLATE_VARIABLES] Пользовательские: {custom_vars}")
        
        # Возвращаем переменные и дополнительную информацию
        response_data = {
            'success': True,
            'variables': all_vars,  # Все переменные
            'system_variables': system_vars,  # Системные переменные
            'custom_variables': custom_vars,  # Пользовательские переменные
            'name': template.name,
            'default_category_id': template.default_category.id if template.default_category else None,
            'default_category_name': template.default_category.title if template.default_category else None,
            'has_title_prompt': bool(template.title_prompt),
            'has_content_prompt': bool(template.content_prompt),
            'has_image_prompt': bool(template.image_prompt),
            'has_additional_section_prompt': bool(template.additional_section_prompt),
            'content_generation_mode': template.content_generation_mode,
            'image_generation_mode': template.image_generation_mode,
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f"Ошибка get_prompt_variables: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


"""AJAX генерация тестовой статьи"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def template_test_generate(request, pk):
    """
    AJAX генерация тестовой статьи с полной поддержкой всех промптов шаблона
    """
    template = get_object_or_404(PromptTemplate, pk=pk)
    
    # ВАЛИДАЦИЯ: Проверяем промпты ТОЛЬКО если соответствующие галочки включены
    if template.generate_title:
        if not template.title_prompt or not template.title_prompt.strip():
            return JsonResponse({
                'success': False,
                'error': 'Промпт для заголовка пустой, но генерация заголовка включена. Отредактируйте шаблон и заполните поле "Промпт для заголовка".'
            }, status=400)
    
    if template.generate_content:
        if not template.content_prompt or not template.content_prompt.strip():
            return JsonResponse({
                'success': False,
                'error': 'Промпт для контента пустой, но генерация контента включена. Отредактируйте шаблон и заполните поле "Промпт для основного контента".'
            }, status=400)
    
    if template.generate_additional_section:
        if not template.additional_section_prompt or not template.additional_section_prompt.strip():
            return JsonResponse({
                'success': False,
                'error': 'Промпт для дополнительной секции пустой, но генерация включена. Отредактируйте шаблон и заполните поле "Промпт для дополнительной секции".'
            }, status=400)
    
    try:
        import json
        data = json.loads(request.body)
        
        keywords = data.get('keywords', '')
        additional_context = data.get('context_data', {})
        category_id = data.get('category_id')
        
        # Получаем категорию
        from Blog.models import Category
        if category_id:
            try:
                category = Category.objects.get(pk=category_id, activ=True)
            except Category.DoesNotExist:
                category = template.default_category
        else:
            category = template.default_category
        
        if not category:
            try:
                category = Category.objects.get(slug='vysoko-intellektualnye-novosti')
            except Category.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Категория не найдена. Укажите категорию в шаблоне или создайте категорию "vysoko-intellektualnye-novosti"'
                }, status=400)
        
        # Если keywords есть в context_data (из переменной {keywords}), используем его
        if 'keywords' in additional_context and additional_context['keywords']:
            keywords = additional_context['keywords']
        
        # Если category есть в context_data (из переменной {category}), используем его для категории
        # Но категория для публикации остается из шаблона
        category_for_context = category.title
        if 'category' in additional_context and additional_context['category']:
            category_for_context = additional_context['category']
            logger.info(f"[TEMPLATE_TEST_GENERATE] Категория переопределена через переменную {{category}}: {category_for_context}")
        
        # Объединяем контекст
        # Базовые системные переменные
        full_context = {
            'keywords': keywords,
        }
        
        # КРИТИЧНО: Не устанавливаем 'category' здесь, т.к. generate_test_article сохранит объект Category в _category_obj
        # А строка для контекста промпта будет установлена из category_for_context
        # Сначала добавляем пользовательские переменные из формы
        full_context.update(additional_context)
        
        # ТОЛЬКО ПОСЛЕ обновления additional_context добавляем category как строку для контекста промпта
        # (чтобы переменная {category} из формы могла переопределить значение)
        if 'category' not in full_context:
            full_context['category'] = category_for_context  # Строка для контекста промпта
        
        logger.info(f"[TEMPLATE_TEST_GENERATE] Контекст для генерации: {list(full_context.keys())}")
        # Безопасное логирование пользовательских переменных (безопасно для Windows cp1251)
        safe_additional_context = {}
        for key, value in additional_context.items():
            if isinstance(value, str):
                # Безопасное преобразование для логирования
                try:
                    safe_value = value.encode('cp1251', errors='ignore').decode('cp1251', errors='ignore')
                except:
                    safe_value = str(value)[:50]  # Ограничиваем длину
            else:
                safe_value = str(value)[:50] if value else ''
            safe_additional_context[key] = safe_value
        logger.info(f"[TEMPLATE_TEST_GENERATE] Пользовательские переменные: {safe_additional_context}")
        logger.info(f"[TEMPLATE_TEST_GENERATE] Категория для публикации: {category.title if hasattr(category, 'title') else category}")
        
        # Создаем уникальный ID для отслеживания прогресса
        import uuid
        progress_id = str(uuid.uuid4())
        
        # Сохраняем начальный прогресс в кэш
        from django.core.cache import cache
        cache.set(f'generation_progress_{progress_id}', {
            'status': 'starting',
            'message': 'Инициализация генерации...',
            'progress': 0,
            'current_step': 'init'
        }, timeout=600)  # 10 минут
        
        # Создаем сервис генерации для тестирования
        generator = ArticleGeneratorService(prompt_template=template)
        
        # Устанавливаем callback для прогресса
        def progress_callback(step, message, progress):
            cache.set(f'generation_progress_{progress_id}', {
                'status': 'in_progress',
                'message': message,
                'progress': progress,
                'current_step': step
            }, timeout=600)
        
        generator.progress_callback = progress_callback
        
        # Генерируем статью (передаём объект Category в параметр category, а строку - в context_data)
        post = generator.generate_test_article(
            category=category,  # Объект Category для публикации
            keywords=keywords,
            context_data=full_context  # Строка 'category' для контекста промпта уже есть в full_context
        )
        
        if not post:
            cache.set(f'generation_progress_{progress_id}', {
                'status': 'error',
                'message': 'Не удалось сгенерировать статью',
                'progress': 0,
                'current_step': 'error'
            }, timeout=600)
            return JsonResponse({
                'success': False,
                'error': 'Не удалось сгенерировать статью',
                'progress_id': progress_id
            }, status=500)
        
        # Добавляем маркер тестовой статьи
        if post.description:
            post.description = f'[TEST_ARTICLE] {post.description}'
        else:
            post.description = '[TEST_ARTICLE]'
        post.save(update_fields=['description'])
        
        # Получаем статистику генерации
        generation_stats = getattr(generator, '_generation_stats', {})
        tokens_used = getattr(generator, '_tokens_used', {})
        usage_data = getattr(generator, '_usage_data', {})
        
        # Рассчитываем стоимость
        from .token_cost_analysis import TokenCostAnalyzer
        cost_analyzer = TokenCostAnalyzer()
        total_cost = 0.0
        tokens_breakdown = {}
        
        for key, tokens in tokens_used.items():
            if tokens > 0:
                model = 'GigaChat'  # Можно получить из usage_data
                cost = cost_analyzer.calculate_cost(model, tokens)
                total_cost += cost
                tokens_breakdown[key] = {
                    'tokens': tokens,
                    'cost': cost
                }
        
        # Сохраняем финальный прогресс
        cache.set(f'generation_progress_{progress_id}', {
            'status': 'completed',
            'message': 'Генерация завершена',
            'progress': 100,
            'current_step': 'completed'
        }, timeout=600)
        
        # Извлекаем дополнительную секцию из контента (если была сгенерирована)
        additional_section_html = None
        content_without_additional = post.content or ''
        
        if hasattr(generator, '_additional_section') and generator._additional_section.get('html'):
            additional_section_html = generator._additional_section['html']
            # Удаляем дополнительную секцию из основного контента для отдельного отображения
            if additional_section_html in content_without_additional:
                content_without_additional = content_without_additional.replace(
                    '\n\n' + additional_section_html, ''
                ).replace(additional_section_html, '').strip()
        
        # Получаем теги
        tags_list = [tag.name for tag in post.tags.all()] if post.tags.exists() else []
        
        return JsonResponse({
            'success': True,
            'post_id': post.id,
            'title': post.title,
            'status': post.status,
            'description': post.description.replace('[TEST_ARTICLE]', '').strip() if post.description else '',
            'image_url': post.kartinka.url if post.kartinka else None,
            'category': post.category.title if post.category else '',
            'created': post.created.isoformat() if post.created else '',
            'content': content_without_additional,  # Полный контент без дополнительной секции
            'content_preview': content_without_additional[:500] if content_without_additional else '',
            'additional_section': additional_section_html,  # Дополнительная секция отдельно
            'tags': tags_list,  # Список тегов
            'word_count': len(content_without_additional.split()) if content_without_additional else 0,
            'progress_id': progress_id,
            'generation_stats': generation_stats,
            'tokens_used': tokens_breakdown,
            'estimated_cost': round(total_cost, 4),
            'edit_url': f'/blog/{post.id}/{post.slug}/edit/' if post.slug else None,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат данных'
        }, status=400)
    except ValueError as e:
        # Ошибки конфигурации или валидации - возвращаем понятное сообщение
        error_msg = str(e)
        logger.error(f"Ошибка генерации тестовой статьи: {error_msg}", exc_info=True)
        
        # Улучшаем сообщение для ошибок GigaChat
        if 'GigaChat не настроен' in error_msg or 'credentials not configured' in error_msg.lower():
            error_msg = "GigaChat не настроен! Настройте AssistantSettings в админ-панели Django:\n" \
                       "1. Зайдите в админ-панель (/admin/)\n" \
                       "2. Откройте Assistant / Assistant Settings\n" \
                       "3. Заполните одно из:\n" \
                       "   - gigachat_authorization_key (новый способ)\n" \
                       "   ИЛИ\n" \
                       "   - gigachat_client_id и gigachat_client_secret (старый способ)"
        
        return JsonResponse({
            'success': False,
            'error': error_msg
        }, status=500)
    except Exception as e:
        logger.error(f"Ошибка генерации тестовой статьи: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Ошибка генерации: {str(e)}'
        }, status=500)


"""Публикация тестовой статьи"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def template_test_publish(request, post_id):
    """Публикация тестовой статьи"""
    from Blog.models import Post
    post = get_object_or_404(Post, pk=post_id, author__username='ai_assistant')
    
    post.status = 'published'
    post.save(update_fields=['status'])
    
    return JsonResponse({
        'success': True,
        'message': 'Статья опубликована'
    })


"""Перевод тестовой статьи в черновик"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def template_test_draft(request, post_id):
    """Перевод тестовой статьи в черновик"""
    from Blog.models import Post
    post = get_object_or_404(Post, pk=post_id, author__username='ai_assistant')
    
    post.status = 'draft'
    post.save(update_fields=['status'])
    
    return JsonResponse({
        'success': True,
        'message': 'Статья переведена в черновик'
    })


"""Установка расписания публикации для тестовой статьи"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def template_test_schedule(request, post_id):
    """
    Создание расписания из тестовой статьи (действие "В очередь")
    """
    from Blog.models import Post
    post = get_object_or_404(Post, pk=post_id, author__username='ai_assistant')
    
    try:
        import json
        data = json.loads(request.body)
        
        schedule_name = data.get('schedule_name', f'Расписание для статьи: {post.title[:50]}')
        frequency = data.get('frequency', 'daily')
        articles_per_run = data.get('articles_per_run', 1)
        schedule_date = data.get('schedule_date')
        schedule_time = data.get('schedule_time')
        
        # Находим шаблон промпта из тестовой статьи
        template = None
        
        # Пытаемся найти шаблон через AIGeneratedArticle
        try:
            ai_article = AIGeneratedArticle.objects.filter(post=post).first()
            if ai_article and ai_article.prompt_template:
                template = ai_article.prompt_template
        except:
            pass
        
        # Если не нашли - берем первый активный шаблон
        if not template:
            template = PromptTemplate.objects.filter(is_active=True).first()
        
        if not template:
            return JsonResponse({
                'success': False,
                'error': 'Не найден активный шаблон промпта'
            }, status=400)
        
        # Создаем расписание
        schedule = AISchedule.objects.create(
            name=schedule_name,
            prompt_template=template,
            category=post.category,
            frequency=frequency,
            articles_per_run=articles_per_run,
            is_active=True,
            created_by=request.user,
            tags=', '.join([tag.name for tag in post.tags.all()]),
            keywords=post.description.replace('[TEST_ARTICLE]', '').strip() if post.description else '',
        )
        
        # Если указана дата и время - устанавливаем next_run
        if schedule_date and schedule_time:
            from datetime import datetime
            schedule_datetime_str = f"{schedule_date} {schedule_time}"
            schedule_datetime = datetime.strptime(schedule_datetime_str, '%Y-%m-%d %H:%M')
            schedule_datetime = timezone.make_aware(schedule_datetime)
            
            if schedule_datetime > timezone.now():
                schedule.next_run = schedule_datetime
                schedule.save(update_fields=['next_run'])
        
        # Настраиваем Django-Q расписание
        from .signals import setup_ai_schedule
        setup_ai_schedule(sender=AISchedule, instance=schedule, created=True)
        
        return JsonResponse({
            'success': True,
            'message': f'Расписание "{schedule.name}" создано успешно',
            'schedule_id': schedule.id,
            'schedule_url': f'/assistant/dashboard/schedules/{schedule.id}/edit/'
        })
        
    except Exception as e:
        logger.error(f"Ошибка создания расписания из тестовой статьи: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Ошибка создания расписания: {str(e)}'
        }, status=500)


"""Функция для публикации запланированной статьи (вызывается Django-Q)"""
def publish_scheduled_post(post_id):
    """Функция для публикации запланированной статьи (вызывается Django-Q)"""
    from Blog.models import Post
    try:
        post = Post.objects.get(pk=post_id)
        post.status = 'published'
        post.save(update_fields=['status'])
        logger.info(f"Статья {post_id} опубликована по расписанию")
    except Post.DoesNotExist:
        logger.error(f"Статья {post_id} не найдена для публикации по расписанию")
    except Exception as e:
        logger.error(f"Ошибка публикации статьи {post_id} по расписанию: {str(e)}")


"""Удаление тестовой статьи"""
@login_required
@user_passes_test(is_superuser)
@require_POST
def template_test_delete(request, post_id):
    """Удаление тестовой статьи"""
    from Blog.models import Post
    post = get_object_or_404(Post, pk=post_id, author__username='ai_assistant')
    
    post_title = post.title
    post.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Статья "{post_title}" удалена'
    })


"""Предпросмотр промптов с подставленными переменными"""
@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def template_preview_prompts(request, pk):
    """
    Предпросмотр всех промптов шаблона с подставленными переменными
    """
    template = get_object_or_404(PromptTemplate, pk=pk)
    
    try:
        data = json.loads(request.body)
        additional_context = data.get('context_data', {})
        category_id = data.get('category_id')
        
        # Получаем категорию (используем default_category из шаблона, если не указана)
        from Blog.models import Category
        category = template.default_category
        if category_id:
            try:
                category = Category.objects.get(pk=category_id, activ=True)
            except Category.DoesNotExist:
                category = template.default_category
        else:
            category = template.default_category
        
        if not category:
            try:
                category = Category.objects.get(slug='vysoko-intellektualnye-novosti')
            except Category.DoesNotExist:
                category = None
        
        # Подготавливаем контекст
        keywords = data.get('keywords', '')
        if 'keywords' in additional_context and additional_context['keywords']:
            keywords = additional_context['keywords']
        
        category_for_context = category.title if category else ''
        if 'category' in additional_context and additional_context['category']:
            category_for_context = additional_context['category']
        
        full_context = {
            'category': category_for_context,
            'keywords': keywords,
        }
        full_context.update(additional_context)
        
        # Форматируем промпты
        previews = {}
        
        if template.generate_title and template.title_prompt:
            try:
                previews['title'] = template.format_prompt(template.title_prompt, full_context)
            except Exception as e:
                previews['title'] = f'Ошибка форматирования: {str(e)}'
        else:
            previews['title'] = None
        
        if template.generate_content and template.content_prompt:
            try:
                # Добавляем title в контекст для content_prompt
                context_with_title = {**full_context, 'title': 'Пример заголовка'}
                previews['content'] = template.format_prompt(template.content_prompt, context_with_title)
            except Exception as e:
                previews['content'] = f'Ошибка форматирования: {str(e)}'
        else:
            previews['content'] = None
        
        if template.generate_image and template.image_prompt:
            try:
                context_with_title = {**full_context, 'title': 'Пример заголовка'}
                previews['image'] = template.format_prompt(template.image_prompt, context_with_title)
            except Exception as e:
                previews['image'] = f'Ошибка форматирования: {str(e)}'
        else:
            previews['image'] = None
        
        if template.generate_additional_section and template.additional_section_prompt:
            try:
                context_with_content = {**full_context, 'title': 'Пример заголовка', 'content': 'Пример контента'}
                previews['additional_section'] = template.format_prompt(template.additional_section_prompt, context_with_content)
            except Exception as e:
                previews['additional_section'] = f'Ошибка форматирования: {str(e)}'
        else:
            previews['additional_section'] = None
        
        # Проверяем валидность переменных
        missing_vars = []
        all_prompts = [previews.get('title'), previews.get('content'), previews.get('image'), previews.get('additional_section')]
        for prompt in all_prompts:
            if prompt and '{' in prompt:
                import re
                vars_in_prompt = re.findall(r'\{([^}]+)\}', prompt)
                for var in vars_in_prompt:
                    if var not in full_context:
                        if var not in missing_vars:
                            missing_vars.append(var)
        
        return JsonResponse({
            'success': True,
            'previews': previews,
            'context': full_context,
            'missing_variables': missing_vars,
            'warnings': missing_vars if missing_vars else []
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат данных'
        }, status=400)
    except Exception as e:
        logger.error(f"Ошибка предпросмотра промптов: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Ошибка предпросмотра: {str(e)}'
        }, status=500)


"""Получение прогресса генерации статьи"""
@login_required
@user_passes_test(is_superuser)
def template_generation_progress(request, progress_id):
    """
    Получение текущего прогресса генерации статьи
    """
    from django.core.cache import cache
    
    progress_data = cache.get(f'generation_progress_{progress_id}')
    
    if not progress_data:
        return JsonResponse({
            'success': False,
            'error': 'Прогресс не найден или истек'
        }, status=404)
    
    return JsonResponse({
        'success': True,
        'progress': progress_data
    })