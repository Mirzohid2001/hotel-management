from django.urls import path

from . import views

app_name = "hr"

urlpatterns = [
    path("employees/", views.employee_list, name="employees"),
    path("employees/new/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
    path("employees/<int:pk>/advance/", views.employee_advance, name="employee_advance"),
    path("employees/<int:pk>/pay/", views.employee_pay, name="employee_pay"),
    path("payroll/", views.payroll_list, name="payroll_list"),
    path("payroll/generate/", views.payroll_generate, name="payroll_generate"),
    path("payroll/pay-all/", views.payroll_pay_all, name="payroll_pay_all"),
    path("payroll/<int:pk>/finalize/", views.payroll_finalize, name="payroll_finalize"),
    path("payroll/items/<int:item_id>/edit/", views.payroll_item_edit, name="payroll_item_edit"),
    path("payroll/items/<int:item_id>/pay/", views.payroll_pay_item, name="payroll_pay"),
    path("advances/", views.advance_list, name="advances"),
    path("advances/new/", views.advance_create, name="advance_create"),
    path("advances/<int:pk>/settle/", views.advance_settle, name="advance_settle"),
]
