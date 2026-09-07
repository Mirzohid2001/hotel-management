from django.urls import path

from . import views

app_name = "guests"

urlpatterns = [
    path("", views.guest_list, name="list"),
    path("new/", views.guest_create, name="create"),
    path("quick/guest/", views.guest_quick_create, name="quick_guest"),
    path("quick/company/", views.company_quick_create, name="quick_company"),
    path("companies/", views.company_list, name="company_list"),
    path("companies/new/", views.company_create, name="company_create"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("<int:pk>/", views.guest_detail, name="detail"),
    path("<int:pk>/edit/", views.guest_edit, name="edit"),
    path("<int:pk>/documents/", views.guest_add_document, name="add_document"),
    path("<int:pk>/notes/", views.guest_add_note, name="add_note"),
]
