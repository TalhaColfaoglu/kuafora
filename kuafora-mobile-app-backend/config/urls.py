from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from app.barbers.views import ToggleTodayApi
from app.users.views import ResolveUserView
from app.subscriptions.views import SubscriptionViewSet
from django.http import JsonResponse, FileResponse
from pathlib import Path

def health(request):
    return JsonResponse({"status": "ok"})

def schema_static(request):
    # Önce statik YAML şemayı sunmayı dene; yoksa dinamik üretime düş
    try:
        if getattr(settings, "STATIC_ROOT", None):
            p = Path(settings.STATIC_ROOT) / "openapi.yaml"
            if p.exists():
                return FileResponse(open(p, "rb"), content_type="application/yaml")
    except Exception:
        # Statik şema okunamazsa sessizce dinamik şemaya düş
        pass

    # Dinamik fallback (JSON döner) - hata olursa bile 200 ve minimal şema dön
    try:
        return SpectacularAPIView.as_view()(request)
    except Exception as exc:
        # Dinamik üretim dahi patlarsa, minimal ama geçerli bir OpenAPI şeması ile cevap ver
        # Böylece /api/schema/ ve /api/docs/ asla 500 vermez.
        minimal_schema = {
            "openapi": "3.0.0",
            "info": {
                "title": "Kuafora API",
                "version": "1.0.0",
                "description": "Schema generation failed, serving minimal fallback schema instead.",
            },
            "paths": {},
        }
        return JsonResponse(minimal_schema, status=200)

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
    # Explicit subscription aliases for vitrin app (before subscriptions router to avoid conflicts)
    path(
        "api/partner/subscriptions/my_subscription/",
        SubscriptionViewSet.as_view({"get": "my_subscription"}),
        name="api-partner-subscriptions-my-subscription",
    ),
    path(
        "api/partner/subscriptions/start-trial/",
        SubscriptionViewSet.as_view({"post": "start_trial"}),
        name="api-partner-subscriptions-start-trial",
    ),
    # Alias for /api/subscriptions/my_subscription/ (router action)
    path(
        "api/subscriptions/my_subscription/",
        SubscriptionViewSet.as_view({"get": "my_subscription"}),
        name="api-subscriptions-my-subscription",
    ),
    path("api/barbershops/<int:barbershop_id>/toggle/", ToggleTodayApi.as_view(), name="api-barbershops-toggle-by-id"),
    path("api/auth/", include("app.users.urls")),
    # Public + partner APIs
    path("api/", include(("app.barbers.urls", "barbers"))),
    path("", include(("app.appointments.urls", "appointments"))),
    path("api/", include(("app.uploads.urls", "uploads"))),
    path("api/", include(("app.campaigns.urls", "campaigns"))),
    path("api/", include(("app.chat.urls", "chat"))),
    path("api/", include(("app.notifications.urls", "notifications"))),
    path("api/", include(("app.subscriptions.urls", "subscriptions"))),
    path("api/", include(("app.search.urls", "search"))),
    path("api/users/resolve/", ResolveUserView.as_view(), name="resolve-user"),
    path("health/", health),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
