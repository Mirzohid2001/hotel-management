from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("expired/", views.expired, name="expired"),
]
