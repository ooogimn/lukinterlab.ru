from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import WikiAttachment, WikiPage


class WikiAttachmentInline(admin.TabularInline):
    model = WikiAttachment
    extra = 1


@admin.register(WikiPage)
class WikiPageAdmin(TreeAdmin):
    form = movenodeform_factory(WikiPage)
    list_display = ("title", "slug", "updated_at")
    search_fields = ("title", "slug", "content")
    inlines = [WikiAttachmentInline]


@admin.register(WikiAttachment)
class WikiAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "page", "file", "external_url", "created_at")
    search_fields = ("page__title", "page__slug", "file", "external_url")
