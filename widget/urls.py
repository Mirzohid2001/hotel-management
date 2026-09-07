from django.urls import path

from . import views

app_name = "widget"

urlpatterns = [
    path(
        "api/<slug:tenant_slug>/<slug:branch_code>/availability/",
        views.api_availability,
        name="api_availability",
    ),
    path(
        "api/<slug:tenant_slug>/<slug:branch_code>/book/",
        views.api_book,
        name="api_book",
    ),
    path(
        "api/<slug:tenant_slug>/availability/",
        views.api_availability,
        name="api_availability_legacy",
    ),
    path(
        "api/<slug:tenant_slug>/book/",
        views.api_book,
        name="api_book_legacy",
    ),
    path("<slug:tenant_slug>/<slug:branch_code>/", views.widget_frame, name="frame"),
    path("<slug:tenant_slug>/", views.widget_legacy_redirect, name="frame_legacy"),
]
