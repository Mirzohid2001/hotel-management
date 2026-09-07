from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    path("", views.service_list, name="list"),
    path("new/", views.service_create, name="create"),
    path("<int:pk>/edit/", views.service_edit, name="edit"),
    path("order/", views.service_order, name="order"),
]
