"""
Кэш дерева категорий блога (сайдбар) и счётчика опубликованных статей.
Инвалидация при изменении категорий и постов.
"""
from django.core.cache import cache
from django.db.models import Q, Count
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

CATEGORY_TREE_CACHE_KEY = 'blog:category_tree:v2'
BLOG_PUBLISHED_COUNT_CACHE_KEY = 'blog:published_post_count:v1'
CATEGORY_TREE_TTL = 3600
PUBLISHED_COUNT_TTL = 300


def category_subtree_ids(category):
    """ID категории и всех потомков (MPTT) для фильтрации статей по «ветке»."""
    return [category.pk] + list(category.get_descendants().values_list('pk', flat=True))


def _category_sidebar_dict(cat):
    """Сериализуемый узел категории для шаблона (без ORM в Redis)."""
    img_url = ''
    if cat.kartinka_cat:
        try:
            img_url = cat.kartinka_cat.url
        except (ValueError, OSError):
            img_url = ''
    return {
        'id': cat.pk,
        'title': cat.title,
        'kartinka_cat_url': img_url,
    }


def _category_sidebar_child_nodes(parent):
    """Рекурсивное дерево для сайдбара: узел виден, если в нём или ниже есть статьи."""
    nodes = []
    for c in parent.get_children().annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).order_by('lft'):
        sub = _category_sidebar_child_nodes(c)
        if c.post_count > 0 or sub:
            nodes.append({'category': _category_sidebar_dict(c), 'children': sub})
    return nodes


def _build_blog_category_tree():
    """Корни MPTT с детьми для левого сайдбара блога (без кэша)."""
    from .models import Category

    tree = []
    for root in Category.objects.filter(parent__isnull=True).annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    ).order_by('tree_id', 'lft'):
        children = _category_sidebar_child_nodes(root)
        if root.post_count > 0 or children:
            tree.append({'category': _category_sidebar_dict(root), 'children': children})
    return tree


def get_cached_blog_category_tree():
    tree = None
    try:
        tree = cache.get(CATEGORY_TREE_CACHE_KEY)
    except Exception:
        tree = None
    if not tree:
        tree = _build_blog_category_tree()
        try:
            cache.set(CATEGORY_TREE_CACHE_KEY, tree, CATEGORY_TREE_TTL)
        except Exception:
            pass
    return tree


def get_cached_published_post_count():
    n = None
    try:
        n = cache.get(BLOG_PUBLISHED_COUNT_CACHE_KEY)
    except Exception:
        n = None
    if n is None:
        from .models import Post

        n = Post.objects.filter(status='published').count()
        try:
            cache.set(BLOG_PUBLISHED_COUNT_CACHE_KEY, n, PUBLISHED_COUNT_TTL)
        except Exception:
            pass
    return int(n)


def invalidate_blog_sidebar_cache():
    try:
        cache.delete('blog:category_tree:v1')
        cache.delete(CATEGORY_TREE_CACHE_KEY)
        cache.delete(BLOG_PUBLISHED_COUNT_CACHE_KEY)
    except Exception:
        pass


from .models import Category as _Category, Post as _Post  # noqa: E402


@receiver([post_save, post_delete], sender=_Category)
def _on_category_change(sender, **kwargs):
    if kwargs.get('raw'):
        return
    invalidate_blog_sidebar_cache()


@receiver([post_save, post_delete], sender=_Post)
def _on_post_change(sender, **kwargs):
    if kwargs.get('raw'):
        return
    invalidate_blog_sidebar_cache()
