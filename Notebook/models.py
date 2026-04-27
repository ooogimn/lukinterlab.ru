from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from treebeard.mp_tree import MP_Node
from home.media_utils import resolve_external_media


def wiki_attachment_upload_to(instance, filename):
    if instance.page_id:
        return f"{instance.page.get_folder_path()}attachments/{filename}"
    return f"wiki/unassigned/attachments/{filename}"


class WikiPage(MP_Node):
    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Slug", max_length=255)
    content = RichTextUploadingField("Содержимое", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    node_order_by = ["title"]

    class Meta:
        verbose_name = "Wiki страница"
        verbose_name_plural = "Wiki страницы"

    def __str__(self):
        return self.title

    def get_folder_path(self):
        slugs = [ancestor.slug for ancestor in self.get_ancestors()]
        slugs.append(self.slug)
        relative = "/".join(filter(None, slugs))
        return f"wiki/{relative}/"


class WikiAttachment(models.Model):
    page = models.ForeignKey(
        WikiPage,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Страница",
    )
    file = models.FileField("Файл", upload_to=wiki_attachment_upload_to, blank=True, null=True)
    external_url = models.URLField(
        "Внешняя ссылка",
        max_length=500,
        blank=True,
        help_text="YouTube / Rutube / VK Video или прямая ссылка на изображение.",
    )
    created_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        verbose_name = "Вложение Wiki"
        verbose_name_plural = "Вложения Wiki"

    def __str__(self):
        if self.file:
            return self.file.name.rsplit("/", 1)[-1]
        return self.external_url or f"Attachment #{self.pk}"

    def get_kind(self):
        if self.external_url:
            resolved = resolve_external_media(self.external_url)
            if resolved:
                return "video" if resolved.kind == "video" else "image"
            return "link"
        if not self.file:
            return "file"
        lower_name = self.file.name.lower()
        if lower_name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")):
            return "image"
        if lower_name.endswith((".mp4", ".webm", ".ogg", ".mov", ".m4v")):
            return "video"
        return "file"
