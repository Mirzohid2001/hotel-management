from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create, name="create"),
    path("spend/new/", views.spend_create, name="spend_create"),
    path("spend/<int:pk>/void/", views.spend_void, name="spend_void"),
    path("<int:pk>/edit/", views.ticket_edit, name="edit"),
    path("<int:pk>/assign/", views.ticket_assign, name="assign"),
    path("<int:pk>/complete/", views.ticket_complete, name="complete"),
    path("<int:pk>/cancel/", views.ticket_cancel, name="cancel"),
]
