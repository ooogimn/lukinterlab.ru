from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import WikiAttachmentForm, WikiPageForm
from .models import WikiAttachment
from .models import WikiPage
from home.media_utils import resolve_external_media


def _build_tree_for_root(root_page):
    pages = list(root_page.get_tree())
    nodes_by_path = {}
    for page in pages:
        nodes_by_path[page.path] = {"page": page, "children": [], "has_attachments_branch": False}

    for page in pages:
        if page.pk == root_page.pk:
            continue
        parent_path = page.path[:-page.steplen]
        parent_node = nodes_by_path.get(parent_path)
        if parent_node:
            parent_node["children"].append(nodes_by_path[page.path])

    def _sort_sidebar_children(n):
        n["children"].sort(key=lambda x: (x["page"].title or "").casefold())
        for c in n["children"]:
            _sort_sidebar_children(c)

    root_node = nodes_by_path[root_page.path]
    _sort_sidebar_children(root_node)
    return root_node


def _mark_attachments_branch(node, attachment_page_ids):
    own = node["page"].id in attachment_page_ids
    child_has = False
    for child in node["children"]:
        child_has = _mark_attachments_branch(child, attachment_page_ids) or child_has
    node["has_attachments_branch"] = own or child_has
    return node["has_attachments_branch"]


def _resolve_root_by_slug(notebook_slug):
    return get_object_or_404(
        WikiPage,
        depth=1,
        slug=notebook_slug,
    )


def _render_notebook_workspace(request, root_page, selected_page=None):
    if selected_page is None:
        selected_page = root_page

    if selected_page.pk != root_page.pk and not selected_page.is_descendant_of(root_page):
        raise Http404("Выбранная страница не принадлежит этому блокноту.")

    sidebar_tree = _build_tree_for_root(root_page)
    expanded_ids = set(
        selected_page.get_ancestors().values_list("id", flat=True)
    )
    expanded_ids.add(selected_page.id)

    attachment_form = WikiAttachmentForm()
    attachment_page_ids = set(
        WikiAttachment.objects.filter(page__in=root_page.get_tree()).values_list("page_id", flat=True)
    )
    _mark_attachments_branch(sidebar_tree, attachment_page_ids)
    attachment_items = []
    for attachment in selected_page.attachments.all():
        kind = attachment.get_kind()
        url = attachment.file.url if attachment.file else (attachment.external_url or "")
        embed_url = None
        if attachment.external_url:
            resolved = resolve_external_media(attachment.external_url)
            embed_url = resolved.embed_url if resolved else None
        attachment_items.append(
            {
                "id": attachment.id,
                "url": url,
                "embed_url": embed_url,
                "name": attachment.file.name.rsplit("/", 1)[-1] if attachment.file else attachment.external_url,
                "kind": kind,
                "is_external": bool(attachment.external_url),
            }
        )

    context = {
        "title": root_page.title,
        "notebook_root": root_page,
        "selected_page": selected_page,
        "sidebar_tree": sidebar_tree,
        "expanded_ids": expanded_ids,
        "attachment_form": attachment_form,
        "attachment_page_ids": attachment_page_ids,
        "attachment_items": attachment_items,
    }
    return render(request, "notebook/notebook_view.html", context)


def _redirect_to_notebook(page):
    root_page = page.get_root()
    return redirect("Notebook:notebook_page", notebook_id=root_page.pk, page_id=page.pk)


@staff_member_required
def notebook_home(request):
    notebook_roots = WikiPage.get_root_nodes()
    search_query = (request.GET.get("q") or "").strip()
    sort_key = (request.GET.get("sort") or "updated_desc").strip()
    if search_query:
        notebook_roots = notebook_roots.filter(title__icontains=search_query)

    sort_map = {
        "title_asc": "title",
        "title_desc": "-title",
        "created_asc": "created_at",
        "created_desc": "-created_at",
        "updated_asc": "updated_at",
        "updated_desc": "-updated_at",
    }
    notebook_roots = notebook_roots.order_by(sort_map.get(sort_key, "-updated_at"))
    context = {
        "title": "Полка блокнотов",
        "notebook_roots": notebook_roots,
        "search_query": search_query,
        "sort_key": sort_key,
    }
    return render(request, "notebook/home.html", context)


@staff_member_required
def notebook_view(request, notebook_id, page_id=None):
    root_page = get_object_or_404(WikiPage, pk=notebook_id, depth=1)
    if page_id:
        selected_page = get_object_or_404(WikiPage, pk=page_id)
    else:
        first_child = root_page.get_children().first()
        if first_child:
            return redirect(
                "Notebook:notebook_page",
                notebook_id=root_page.pk,
                page_id=first_child.pk,
            )
        selected_page = root_page
    return _render_notebook_workspace(request, root_page, selected_page)


@staff_member_required
def notebook_view_by_slug(request, notebook_slug, page_id=None):
    root_page = _resolve_root_by_slug(notebook_slug)
    if page_id:
        selected_page = get_object_or_404(WikiPage, pk=page_id)
    else:
        first_child = root_page.get_children().first()
        if first_child:
            return redirect(
                "Notebook:notebook_slug_page",
                notebook_slug=root_page.slug,
                page_id=first_child.pk,
            )
        selected_page = root_page
    return _render_notebook_workspace(request, root_page, selected_page)


@staff_member_required
def notebook_page_create_root(request):
    if request.method == "POST":
        form = WikiPageForm(request.POST, request.FILES)
        if form.is_valid():
            page = form.save()
            uploaded_file = request.FILES.get("create_file")
            external_url = (request.POST.get("create_external_url") or "").strip()
            if uploaded_file or external_url:
                WikiAttachment.objects.create(page=page, file=uploaded_file, external_url=external_url)
            messages.success(request, "Корневой блокнот создан.")
            return redirect("Notebook:notebook", notebook_id=page.pk)
    else:
        form = WikiPageForm()
    return render(
        request,
        "notebook/page_form.html",
        {
            "title": "Создать блокнот",
            "form": form,
            "submit_label": "Создать",
            "cancel_href": reverse("Notebook:home"),
        },
    )


@staff_member_required
def notebook_page_create_child(request, parent_id):
    parent = get_object_or_404(WikiPage, pk=parent_id)
    if request.method == "POST":
        form = WikiPageForm(request.POST, request.FILES, initial_parent=parent)
        if form.is_valid():
            page = form.save()
            uploaded_file = request.FILES.get("create_file")
            external_url = (request.POST.get("create_external_url") or "").strip()
            if uploaded_file or external_url:
                WikiAttachment.objects.create(page=page, file=uploaded_file, external_url=external_url)
            messages.success(request, "Подстраница создана.")
            return _redirect_to_notebook(page)
    else:
        form = WikiPageForm(initial_parent=parent)
    return render(
        request,
        "notebook/page_form.html",
        {
            "title": f"Новая подстраница: {parent.title}",
            "form": form,
            "parent": parent,
            "submit_label": "Создать",
            "cancel_href": reverse(
                "Notebook:notebook_page",
                kwargs={"notebook_id": parent.get_root().pk, "page_id": parent.pk},
            ),
        },
    )


@staff_member_required
def notebook_page_edit(request, page_id):
    page = get_object_or_404(WikiPage, pk=page_id)
    if request.method == "POST":
        form = WikiPageForm(request.POST, request.FILES, instance=page)
        if form.is_valid():
            updated_page = form.save()
            messages.success(request, "Страница обновлена.")
            return _redirect_to_notebook(updated_page)
    else:
        form = WikiPageForm(instance=page)
    return render(
        request,
        "notebook/page_form.html",
        {
            "title": f"Редактировать: {page.title}",
            "form": form,
            "page": page,
            "attachment_form": WikiAttachmentForm(),
            "submit_label": "Сохранить",
            "cancel_href": reverse(
                "Notebook:notebook_page",
                kwargs={"notebook_id": page.get_root().pk, "page_id": page.pk},
            ),
        },
    )


@staff_member_required
def notebook_page_delete(request, page_id):
    page = get_object_or_404(WikiPage, pk=page_id)
    if page.depth == 1:
        messages.error(request, "Удаление корневого блокнота доступно только через Django-админку.")
        return redirect("Notebook:home")
    root_page = page.get_root()
    if request.method == "POST":
        page.delete()
        messages.success(request, "Страница удалена.")
        if root_page.pk == page.pk:
            return redirect("Notebook:home")
        return redirect("Notebook:notebook", notebook_id=root_page.pk)
    return render(
        request,
        "notebook/page_confirm_delete.html",
        {"page": page, "title": "Удалить страницу", "root_page": root_page},
    )


@staff_member_required
def notebook_attachment_upload(request, page_id):
    page = get_object_or_404(WikiPage, pk=page_id)
    if request.method != "POST":
        raise Http404
    form = WikiAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.page = page
        attachment.save()
        messages.success(request, "Файл загружен.")
    else:
        messages.error(request, "Не удалось загрузить файл.")
    return _redirect_to_notebook(page)


@staff_member_required
def notebook_attachment_delete(request, page_id, attachment_id):
    page = get_object_or_404(WikiPage, pk=page_id)
    attachment = get_object_or_404(WikiAttachment, pk=attachment_id, page=page)
    if request.method == "POST":
        attachment.delete()
        messages.success(request, "Файл удален.")
    return _redirect_to_notebook(page)


@staff_member_required
def notebook_attachment_download(request, page_id, attachment_id):
    page = get_object_or_404(WikiPage, pk=page_id)
    attachment = get_object_or_404(WikiAttachment, pk=attachment_id, page=page)
    if attachment.file:
        file_name = attachment.file.name.rsplit("/", 1)[-1]
        return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=file_name)
    if attachment.external_url:
        return redirect(attachment.external_url)
    messages.error(request, "У этого вложения нет файла для скачивания.")
    return _redirect_to_notebook(page)
