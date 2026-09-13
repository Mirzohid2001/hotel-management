from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("notifications/open/", views.notify_open, name="notify_open"),
    path("notifications/dismiss/", views.notify_dismiss, name="notify_dismiss"),
]
