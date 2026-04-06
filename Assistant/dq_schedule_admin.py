"""
Кастомная админка django-q Schedule: человекочитаемые подписи.
Запуск статей: один тик ai_schedules_minute_tick (cron * * * * *); записи run_schedule_task на каждое AISchedule не создаются.
"""
from __future__ import annotations

from typing import Optional

from django.contrib import admin

from .models import AISchedule
from .tasks import SCHEDULE_TASK_FUNC, TICK_SCHEDULE_FUNC


def _parse_aischedule_pk(args) -> Optional[int]:
    """Достаёт pk AISchedule из поля args расписания Django-Q."""
    if args is None or args == '':
        return None
    if isinstance(args, int):
        return args
    if isinstance(args, bool):
        return None
    if isinstance(args, (list, tuple)):
        if len(args) == 1:
            return _parse_aischedule_pk(args[0])
        return None
    if isinstance(args, str):
        s = args.strip()
        if s.isdigit():
            return int(s)
        if s.startswith('(') and s.endswith(')'):
            first = s[1:-1].split(',')[0].strip().strip("'\"")
            if first.isdigit():
                return int(first)
    return None


class AssistantDQScheduleAdmin(admin.ModelAdmin):
    """Списки Scheduled tasks с привязкой к AISchedule (название из нашей модели)."""

    list_display = (
        'id',
        'name',
        'assistant_schedule_title',
        'func',
        'schedule_type',
        'cron_display',
        'repeats',
        'cluster',
        'next_run',
        'last_run',
        'success',
    )
    list_display_links = ('id', 'name')
    list_filter = ('next_run', 'schedule_type', 'cluster')
    search_fields = ('name', 'func', 'cron')
    # Редактирование cron вручную не приветствуется — источник правды AISchedule + setup_schedules
    readonly_fields = ('cron',)

    def changelist_view(self, request, extra_context=None):
        self._assistant_schedule_names = dict(
            AISchedule.objects.values_list('id', 'name')
        )
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description='Название (Assistant)')
    def assistant_schedule_title(self, obj):
        if obj.func == TICK_SCHEDULE_FUNC:
            return 'Тик расписаний статей (каждую минуту)'
        if obj.func != SCHEDULE_TASK_FUNC:
            return '—'
        pk = _parse_aischedule_pk(obj.args)
        if pk is None:
            return '—'
        names = getattr(self, '_assistant_schedule_names', {})
        return names.get(pk) or f'⚠ AISchedule id={pk} не найден'

    @admin.display(description='CRON')
    def cron_display(self, obj):
        return obj.cron or '—'


def register_assistant_django_q_schedule_admin():
    """Подмена стандартной админки Schedule после autodiscover django-q."""
    from django.contrib.admin.sites import NotRegistered

    try:
        from django_q.models import Schedule
    except ImportError:
        return

    try:
        admin.site.unregister(Schedule)
    except NotRegistered:
        pass
    admin.site.register(Schedule, AssistantDQScheduleAdmin)
