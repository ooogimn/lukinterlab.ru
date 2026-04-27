from django.urls import path

from .views import (
    notebook_attachment_delete,
    notebook_attachment_upload,
    notebook_home,
    notebook_view,
    notebook_view_by_slug,
    notebook_page_create_child,
    notebook_page_create_root,
    notebook_page_delete,
    notebook_page_edit,
)

app_name = "Notebook"

urlpatterns = [
    path("", notebook_home, name="home"),
    path("create/", notebook_page_create_root, name="page_create_root"),
    path("n/<int:notebook_id>/", notebook_view, name="notebook"),
    path("n/<int:notebook_id>/page/<int:page_id>/", notebook_view, name="notebook_page"),
    path("s/<slug:notebook_slug>/", notebook_view_by_slug, name="notebook_by_slug"),
    path("s/<slug:notebook_slug>/page/<int:page_id>/", notebook_view_by_slug, name="notebook_slug_page"),
    path("<int:page_id>/edit/", notebook_page_edit, name="page_edit"),
    path("<int:page_id>/delete/", notebook_page_delete, name="page_delete"),
    path("<int:parent_id>/create-child/", notebook_page_create_child, name="page_create_child"),
    path("<int:page_id>/attachments/upload/", notebook_attachment_upload, name="attachment_upload"),
    path(
        "<int:page_id>/attachments/<int:attachment_id>/delete/",
        notebook_attachment_delete,
        name="attachment_delete",
    ),
]
