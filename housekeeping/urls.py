from django.urls import path

from . import views

app_name = "housekeeping"

urlpatterns = [
    path("", views.hk_board, name="board"),
    path("rooms/<int:room_id>/status/", views.hk_set_status, name="set_status"),
    path("tasks/<int:task_id>/assign/", views.hk_assign_task, name="assign_task"),
    path("tasks/<int:task_id>/complete/", views.hk_complete_task, name="complete_task"),
    path("rooms/<int:room_id>/maintenance/", views.hk_report_maintenance, name="report_maintenance"),
]
