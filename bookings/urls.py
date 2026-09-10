from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.reservation_list, name="list"),
    path("board/", views.board, name="board"),
    path("calendar/", views.calendar, name="calendar"),
    path("calendar/quick/", views.calendar_quick_book, name="calendar_quick"),
    path("availability/", views.availability_partial, name="availability"),
    path("inquiries/", views.inquiry_list, name="inquiries"),
    path("new/", views.reservation_create, name="create"),
    path("walk-in/", views.walk_in, name="walk_in"),
    path("walk-in/rooms/", views.walk_in_rooms, name="walk_in_rooms"),
    path("referrers/", views.referrer_list, name="referrer_list"),
    path("referrers/quick/", views.referrer_quick_create, name="referrer_quick"),
    path("referrers/new/", views.referrer_create, name="referrer_create"),
    path("referrers/<int:pk>/edit/", views.referrer_edit, name="referrer_edit"),
    path("commission/", views.commission_report, name="commission_report"),
    path("emehmon/", views.emehmon_report, name="emehmon_report"),
    path("emehmon/statement/", views.emehmon_statement, name="emehmon_statement"),
    path(
        "commission/<int:referrer_id>/statement/",
        views.commission_statement,
        name="commission_statement",
    ),
    path(
        "commission/<int:referrer_id>/pay/",
        views.commission_pay,
        name="commission_pay",
    ),
    path("groups/", views.group_list, name="group_list"),
    path("groups/new/", views.group_create, name="group_create"),
    path("groups/<int:pk>/", views.group_detail, name="group_detail"),
    path("<int:pk>/", views.reservation_detail, name="detail"),
    path("<int:pk>/amend/", views.reservation_amend, name="amend"),
    path("<int:pk>/transfer/", views.reservation_transfer, name="transfer"),
    path("<int:pk>/check-in/", views.reservation_check_in, name="check_in"),
    path("<int:pk>/check-out/", views.reservation_check_out, name="check_out"),
    path("<int:pk>/checkout/", views.checkout_modal, name="checkout_modal"),
    path("<int:pk>/confirm/", views.reservation_confirm, name="confirm"),
    path("<int:pk>/cancel/", views.reservation_cancel, name="cancel"),
    path("<int:pk>/no-show/", views.reservation_no_show, name="no_show"),
]
