from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat, name="chat"),
    path("chat/clear/", views.clear_chat, name="clear_chat"),
    path("admin/login/", views.AdminLoginView.as_view(), name="login"),
    path("admin/logout/", views.logout, name="logout"),
    path("admin/library/", views.library_page, name="library"),
    path("admin/convert/", views.convert, name="convert"),
    path("admin/preview/", views.preview, name="preview"),
    path("admin/download/<str:token>/", views.download, name="download"),
    path("admin/remove/<str:document_id>/", views.remove, name="remove"),
    path("admin/appearance/", views.appearance, name="appearance"),
    path("admin/onedrive/", views.onedrive, name="onedrive"),
]
