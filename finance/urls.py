from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.expense_list, name="list"),
    path("new/", views.expense_create, name="create"),
    path("<int:pk>/edit/", views.expense_edit, name="edit"),
    path("<int:pk>/approve/", views.expense_approve, name="approve"),
    path("<int:pk>/reject/", views.expense_reject, name="reject"),
    path("<int:pk>/pay/", views.expense_pay, name="pay"),
    path("<int:pk>/reopen/", views.expense_reopen, name="reopen"),
    path("<int:pk>/delete/", views.expense_delete, name="delete"),
    path("setup/", views.category_list, name="setup"),
    path("setup/categories/new/", views.category_create, name="category_create"),
    path("setup/categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("setup/categories/<int:pk>/toggle/", views.category_toggle, name="category_toggle"),
    path("setup/vendors/new/", views.vendor_create, name="vendor_create"),
    path("setup/vendors/<int:pk>/edit/", views.vendor_edit, name="vendor_edit"),
    path("setup/vendors/<int:pk>/toggle/", views.vendor_toggle, name="vendor_toggle"),
    path("profit/", views.profit_share, name="profit_share"),
    path("profit/partners/new/", views.profit_partner_create, name="profit_partner_create"),
    path("profit/partners/<int:pk>/edit/", views.profit_partner_edit, name="profit_partner_edit"),
    path("profit/withdraw/", views.profit_withdraw, name="profit_withdraw"),
    path("profit/reset/", views.profit_reset, name="profit_reset"),
    path("currencies/", views.exchange_rates, name="exchange_rates"),
    path("currencies/<int:pk>/delete/", views.exchange_rate_delete, name="exchange_rate_delete"),
]
