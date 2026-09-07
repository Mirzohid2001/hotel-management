from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.stock_list, name="list"),
    path("new/", views.stock_create, name="create"),
    path("<int:pk>/edit/", views.stock_edit, name="edit"),
    path("<int:pk>/adjust/", views.stock_adjust, name="adjust"),
    path("minibar/", views.minibar_sale, name="minibar"),
    path("minibar/quick/", views.minibar_quick, name="minibar_quick"),
    path("minibar/quick-item/", views.minibar_item_quick, name="quick_item"),
]
