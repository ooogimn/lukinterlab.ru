from django import template
from django.conf import settings
from Blog.utils import add_nofollow_to_external_links

register = template.Library()


@register.filter(name='nofollow_external')
def nofollow_external(value):
    """
    Фильтр для автоматического добавления rel="nofollow" к внешним ссылкам
    
    Использование в шаблонах:
    {{ comment.content|nofollow_external|safe }}
    """
    if not value:
        return value
    
    return add_nofollow_to_external_links(value)

