from django.urls import path

from . import views

app_name = "properties"

urlpatterns = [
    path("", views.property_list, name="list"),
    path("switch/all/", views.switch_all_properties, name="switch_all"),
    path("switch/<int:pk>/", views.switch_property, name="switch"),
    path("new/", views.property_create, name="create"),
    path("<int:pk>/", views.property_detail, name="detail"),
    path("<int:pk>/settings/", views.property_settings_edit, name="settings"),
    path("<int:property_id>/room-types/new/", views.room_type_create, name="room_type_create"),
    path(
        "<int:property_id>/room-types/seed/",
        views.room_types_seed,
        name="room_types_seed",
    ),
    path(
        "<int:property_id>/room-types/<int:pk>/edit/",
        views.room_type_edit,
        name="room_type_edit",
    ),
    path("<int:property_id>/room-types/quick/", views.room_type_quick, name="room_type_quick"),
    path("<int:property_id>/floors/new/", views.floor_create, name="floor_create"),
    path("<int:property_id>/floors/quick/", views.floor_quick, name="floor_quick"),
    path("<int:property_id>/rooms/new/", views.room_create, name="room_create"),
    path("<int:property_id>/rooms/<int:pk>/edit/", views.room_edit, name="room_edit"),
    path("<int:property_id>/rates/new/", views.rate_plan_create, name="rate_plan_create"),
    path("rates/<int:rate_id>/matrix/", views.rate_matrix, name="rate_matrix"),
    path("rates/<int:rate_id>/seasons/new/", views.season_create, name="season_create"),
]
