from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from app.barbers.views import ToggleTodayApi

from django.http import JsonResponse
def health(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Top-level aliases to avoid router/action conflicts and ensure 2xx on POST
    path("api/toggle-today/", ToggleTodayApi.as_view(), name="api-toggle-today"),
    path("api/calendar/toggle/", ToggleTodayApi.as_view(), name="api-calendar-toggle"),
    path("api/barbershops/today-toggle/", ToggleTodayApi.as_view(), name="api-barbershops-today-toggle"),
    path("api/barbershops/<int:barbershop_id>/toggle/", ToggleTodayApi.as_view(), name="api-barbershops-toggle-by-id"),
    path("api/auth/", include("app.users.urls")),
    path("api/", include("app.barbers.urls")),
    path("api/", include("app.uploads.urls")),
    path("health/", health),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


