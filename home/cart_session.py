"""Счётчик позиций корзины в сессии — меньше запросов в context_processor cart_info."""

SESSION_CART_ITEMS_COUNT_KEY = 'cart_items_count'


def sync_cart_items_count_session(request, cart):
    """Обновить значение после мутации корзины (избегает лишнего COUNT на следующем запросе)."""
    request.session[SESSION_CART_ITEMS_COUNT_KEY] = cart.get_items_count()


def invalidate_cart_items_count_session(request):
    """Сбросить кэш счётчика (например после смены сессии)."""
    request.session.pop(SESSION_CART_ITEMS_COUNT_KEY, None)
