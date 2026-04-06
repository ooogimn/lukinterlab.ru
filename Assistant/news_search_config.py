"""
Чтение настроек поиска новостей из БД (singleton NewsSearchSettings).
Используется Assistant.news_parser и article_generator.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

# Значения «как на сайте по умолчанию» — при сбросе в дашборде и при первом создании строки.
NEWS_SEARCH_SETTINGS_DEFAULTS: Dict[str, Any] = {
    'ddg_query_suffix': 'новости',
    'ddg_search_url_template': 'https://html.duckduckgo.com/html/?q={query}',
    'search_per_source_limit': 18,
    'search_max_collect': 48,
    'search_pool_timeout': 35,
    'search_parallel_max': 6,
    'freshness_hours': 72,
    'penalize_unknown_published': True,
    'rank_random_jitter': True,
    'query_variant_suffixes': '',
    'force_fresh_news_on_content_retry': True,
    'top_list_random_offset_max': 4,
}


def get_news_search_config() -> SimpleNamespace:
    """
    Возвращает namespace с ключами NEWS_* (как раньше в django.conf.settings),
    чтобы не менять обращения в news_parser/article_generator.
    """
    from .models import NewsSearchSettings

    o = NewsSearchSettings.get_solo()
    tpl = (o.ddg_search_url_template or '').strip() or NEWS_SEARCH_SETTINGS_DEFAULTS['ddg_search_url_template']
    return SimpleNamespace(
        NEWS_DDG_QUERY_SUFFIX=(o.ddg_query_suffix or '').strip(),
        NEWS_DDG_SEARCH_URL_TEMPLATE=tpl,
        NEWS_SEARCH_PER_SOURCE_LIMIT=int(o.search_per_source_limit or 18),
        NEWS_SEARCH_MAX_COLLECT=int(o.search_max_collect or 48),
        NEWS_SEARCH_POOL_TIMEOUT=float(o.search_pool_timeout or 35),
        NEWS_SEARCH_PARALLEL_MAX=max(1, int(o.search_parallel_max or 6)),
        NEWS_FRESHNESS_HOURS=int(o.freshness_hours or 0),
        NEWS_PENALIZE_UNKNOWN_PUBLISHED=bool(o.penalize_unknown_published),
        NEWS_RANK_RANDOM_JITTER=bool(o.rank_random_jitter),
        NEWS_QUERY_VARIANT_SUFFIXES=(o.query_variant_suffixes or '').strip(),
        NEWS_FORCE_FRESH_NEWS_ON_CONTENT_RETRY=bool(o.force_fresh_news_on_content_retry),
        NEWS_TOP_LIST_RANDOM_OFFSET_MAX=int(o.top_list_random_offset_max or 0),
    )
