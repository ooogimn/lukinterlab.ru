# GIN (pg_trgm) для ускорения поиска по title/description блога.

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Blog', '0020_category_blog_category_tree_id_lft_idx_and_more'),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name='post',
            index=GinIndex(
                fields=['title'],
                name='Blog_post_title_trgm',
                opclasses=['gin_trgm_ops'],
            ),
        ),
        migrations.AddIndex(
            model_name='post',
            index=GinIndex(
                fields=['description'],
                name='Blog_post_description_trgm',
                opclasses=['gin_trgm_ops'],
            ),
        ),
    ]
