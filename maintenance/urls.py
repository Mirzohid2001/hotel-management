from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create, name="create"),
    path("statement/", views.statement, name="statement"),
    path("spend/new/", views.spend_create, name="spend_create"),
    path("spend/<int:pk>/edit/", views.spend_edit, name="spend_edit"),
    path("spend/<int:pk>/print/", views.spend_print, name="spend_print"),
    path("spend/<int:pk>/void/", views.spend_void, name="spend_void"),
    path("spend/<int:pk>/delete/", views.spend_delete, name="spend_delete"),
    path("<int:pk>/edit/", views.ticket_edit, name="edit"),
    path("<int:pk>/assign/", views.ticket_assign, name="assign"),
    path("<int:pk>/complete/", views.ticket_complete, name="complete"),
    path("<int:pk>/cancel/", views.ticket_cancel, name="cancel"),
    path("<int:pk>/delete/", views.ticket_delete, name="delete"),
]
