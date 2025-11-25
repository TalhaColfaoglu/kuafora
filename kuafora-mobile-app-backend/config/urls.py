from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from app.barbers.views import ToggleTodayApi
from app.users.views import ResolveUserView
from django.http import JsonResponse, FileResponse
from pathlib import Path

def health(request):
    return JsonResponse({"status": "ok"})

def schema_static(request):
    # Önce statik YAML şemayı sunmayı dene; yoksa dinamik üretime düş
    from django.conf import settings
    p: Path = settings.STATIC_ROOT / "openapi.yaml"
    if p.exists():
        try:
            return FileResponse(open(p, "rb"), content_type="application/yaml")
        except Exception:
            pass
    # Dinamik fallback (JSON döner)
    try:
        return SpectacularAPIView.as_view()(request)
    except Exception as exc:
        # Dinamik üretim dahi patlarsa anlamlı bir hata dön
        return JsonResponse(
            {"detail": "schema generation failed", "error": str(exc)},
            status=500,
        )

urlpatterns = [
    path("admin/", admin.site.urls),
    # Dinamik şema yerine statik dosyayı servis et (dinamik jeneratör hatalarından etkilenmesin)
    path("api/schema/", schema_static, name="schema"),
    # Debug amaçlı dinamik şema (üretimde daima statik kullan)
    path("api/schema-dynamic/", SpectacularAPIView.as_view(), name="schema-dynamic"),
    # Swagger'ı doğrudan statik OpenAPI dosyasından okut (dinamik şema hatalarından etkilenmesin)
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Fallback: Swagger'ı statik üretilmiş dosyadan da servis edebil
    path("api/docs-static/", SpectacularSwaggerView.as_view(url="/static/openapi.yaml"), name="swagger-ui-static"),
    # Top-level aliases to avoid router/action conflicts and ensure 2xx on POST
    path("api/toggle-today/", ToggleTodayApi.as_view(), name="api-toggle-today"),
    path("api/calendar/toggle/", ToggleTodayApi.as_view(), name="api-calendar-toggle"),
    path("api/barbershops/today-toggle/", ToggleTodayApi.as_view(), name="api-barbershops-today-toggle"),
    path("api/barbershops/<int:barbershop_id>/toggle/", ToggleTodayApi.as_view(), name="api-barbershops-toggle-by-id"),
    path("api/auth/", include("app.users.urls")),
    path("api/", include("app.barbers.urls")),
    path("api/", include("app.uploads.urls")),
    # Legacy alias: eski istemciler /api/users/resolve/ beklediği için
    path("api/users/resolve/", ResolveUserView.as_view(), name="api-users-resolve-legacy"),
    path("", include("app.appointments.urls")),
    path("health/", health),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
