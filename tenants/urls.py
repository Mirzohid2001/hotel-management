from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("switch/<int:tenant_id>/", views.switch_tenant, name="switch"),
    path("no-access/", views.no_access, name="no_access"),
    path("staff/", views.staff_list, name="staff_list"),
    path("staff/invite/", views.staff_invite, name="staff_invite"),
    path("staff/<int:pk>/edit/", views.staff_edit, name="staff_edit"),
]
