from django.urls import path

from . import views

app_name = "folio"

urlpatterns = [
    path("reservation/<int:reservation_id>/", views.folio_detail, name="detail"),
    path("reservation/<int:reservation_id>/payment/", views.folio_payment_modal, name="payment_modal"),
    path("reservation/<int:reservation_id>/deposit/", views.folio_deposit, name="deposit"),
    path("reservation/<int:reservation_id>/emehmon/", views.folio_emehmon, name="emehmon"),
    path("<int:pk>/charges/", views.folio_add_charge, name="add_charge"),
    path("<int:pk>/payments/", views.folio_add_payment, name="add_payment"),
    path("<int:pk>/split/", views.folio_add_split, name="add_split"),
    path("<int:pk>/service/", views.folio_post_service, name="post_service"),
    path("<int:pk>/minibar/", views.folio_post_minibar, name="post_minibar"),
    path("charges/<int:pk>/void/", views.folio_void_charge, name="void_charge"),
    path("payments/<int:pk>/void/", views.folio_void_payment, name="void_payment"),
    path("<int:pk>/close/", views.folio_close, name="close"),
    path("<int:pk>/receipt/", views.folio_receipt, name="receipt"),
    path("<int:pk>/pdf/", views.folio_pdf, name="pdf"),
    path("<int:pk>/to-company/", views.folio_to_city_ledger, name="to_company"),
    path("city-ledger/", views.city_ledger_list, name="city_ledger"),
    path("city-ledger/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("city-ledger/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("city-ledger/<int:pk>/pay/", views.invoice_add_payment, name="invoice_pay"),
    path("cash-shift/", views.cash_shift_page, name="cash_shift"),
    path("cash-shift/open/", views.cash_shift_open, name="cash_shift_open"),
    path("cash-shift/close/", views.cash_shift_close, name="cash_shift_close"),
    path("cash-shift/movement/", views.cash_shift_movement, name="cash_shift_movement"),
    path("cash-shift/<int:pk>/print/", views.cash_shift_print, name="cash_shift_print"),
    path("cash-shift/<int:pk>/", views.cash_shift_detail, name="cash_shift_detail"),
]
