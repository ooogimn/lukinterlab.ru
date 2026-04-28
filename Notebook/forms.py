from django import forms
from django.utils.text import slugify
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from home.media_utils import resolve_external_media

from .models import WikiAttachment, WikiPage


class WikiPageForm(forms.Form):
    title = forms.CharField(
        label="Заголовок",
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 "
                "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            }
        ),
    )
    parent = forms.ModelChoiceField(
        label="Родительская страница",
        queryset=WikiPage.objects.all(),
        required=False,
        empty_label="Корневой блокнот",
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 "
                "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            }
        ),
    )
    content = forms.CharField(
        label="Содержимое",
        required=False,
        widget=CKEditorUploadingWidget(config_name="default"),
    )
    avatar = forms.ImageField(
        label="Аватар блокнота",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "w-full rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 "
                "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            }
        ),
    )

    def __init__(self, *args, instance=None, initial_parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.initial_parent = initial_parent
        self.fields["parent"].queryset = WikiPage.objects.all()
        if self.instance:
            self.fields["parent"].queryset = WikiPage.objects.exclude(pk=self.instance.pk)
            self.initial.setdefault("title", self.instance.title)
            self.initial.setdefault("content", self.instance.content)
            self.initial.setdefault("parent", self.instance.get_parent())
            self.initial.setdefault("avatar", self.instance.avatar)
        elif self.initial_parent:
            self.initial.setdefault("parent", self.initial_parent)

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if not self.instance or not parent:
            return parent
        if parent.pk == self.instance.pk:
            raise forms.ValidationError("Нельзя выбрать текущую страницу родителем.")
        if parent.is_descendant_of(self.instance):
            raise forms.ValidationError("Нельзя переносить страницу внутрь ее дочернего узла.")
        return parent

    def _build_unique_slug(self, title, parent=None):
        base = slugify(title, allow_unicode=True) or "note"
        candidate = base
        counter = 2
        siblings = WikiPage.get_root_nodes() if parent is None else parent.get_children()
        sibling_qs = siblings.exclude(pk=self.instance.pk) if self.instance else siblings
        while sibling_qs.filter(slug=candidate).exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    def save(self):
        title = self.cleaned_data["title"].strip()
        content = self.cleaned_data.get("content", "")
        parent = self.cleaned_data.get("parent")
        avatar = self.cleaned_data.get("avatar")
        if not self.instance and parent is None and self.initial_parent is not None:
            parent = self.initial_parent
        # Редактирование: в шаблоне поле parent часто не выводят — в POST ключа нет, cleaned parent=None.
        # None нельзя трактовать как «перенести у корня в новый блокнот» (ветка move(root, sorted-sibling)).
        if self.instance and parent is None and self.instance.get_parent() is not None:
            if not self.data or "parent" not in self.data:
                parent = self.instance.get_parent()
        slug = self._build_unique_slug(title, parent=parent)

        if self.instance:
            page = self.instance
            page.title = title
            page.content = content
            page.slug = slug
            if page.depth == 1:
                if avatar:
                    page.avatar = avatar
                elif self.cleaned_data.get("avatar") is False:
                    page.avatar = None
            page.save()

            current_parent = page.get_parent()
            if parent != current_parent:
                if parent:
                    page.move(parent, pos="sorted-child")
                else:
                    root = page.get_root()
                    if page.pk != root.pk:
                        page.move(root, pos="sorted-sibling")
            return page

        if parent:
            return parent.add_child(title=title, slug=slug, content=content)
        return WikiPage.add_root(title=title, slug=slug, content=content, avatar=avatar)


class WikiAttachmentForm(forms.ModelForm):
    class Meta:
        model = WikiAttachment
        fields = ("file", "external_url")
        widgets = {
            "file": forms.ClearableFileInput(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 "
                    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                }
            ),
            "external_url": forms.URLInput(
                attrs={
                    "class": "w-full rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 "
                    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none",
                    "placeholder": "https://youtube.com/... / rutube / vk video / image url",
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()
        file_obj = cleaned.get("file")
        external_url = (cleaned.get("external_url") or "").strip()
        if not file_obj and not external_url:
            raise forms.ValidationError("Добавьте файл или внешнюю ссылку.")
        if external_url and not resolve_external_media(external_url):
            raise forms.ValidationError("Неподдерживаемая ссылка. Допустимо: YouTube, Rutube, VK Video или прямая ссылка на изображение.")
        cleaned["external_url"] = external_url
        return cleaned
