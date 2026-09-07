from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/", include("accounts.urls")),
    path("tenants/", include("tenants.urls")),
    path("subscriptions/", include("subscriptions.urls")),
    path("properties/", include("properties.urls")),
    path("guests/", include("guests.urls")),
    path("bookings/", include("bookings.urls")),
    path("folio/", include("folio.urls")),
    path("housekeeping/", include("housekeeping.urls")),
    path("finance/", include("finance.urls")),
    path("hr/", include("hr.urls")),
    path("services/", include("services.urls")),
    path("inventory/", include("inventory.urls")),
    path("maintenance/", include("maintenance.urls")),
    path("widget/", include("widget.urls")),
    path("", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Hotel PMS Platform"
admin.site.site_title = "Hotel PMS Admin"
