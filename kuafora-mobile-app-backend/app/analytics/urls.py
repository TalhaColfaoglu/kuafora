from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.analytics.views import TrackingViewSet, AnalyticsViewSet

router = DefaultRouter()
router.register(r"tracking", TrackingViewSet, basename="tracking")
router.register(r"analytics", AnalyticsViewSet, basename="analytics")

urlpatterns = [
    # Mobil uygulama şu anda `/api/analytics/tracking/session` (trailing slash OLMADAN) endpoint'ine POST atıyor.
    # DRF router varsayılan olarak `/tracking/session/` beklediği için bu istek 404 dönüyordu ve
    # `UserSession` kayıtları hiç oluşmadığı için admin panelinde aktif kullanıcı metrikleri 0 görünüyordu.
    #
    # Aşağıdaki alias, trailing slash OLMADAN gelen isteği doğrudan `track_session` action'ına yönlendirir.
    # Böylece mevcut mobil client'ı değiştirmeden oturum verileri toplanır ve dashboard metrikleri çalışır.
    path(
        "tracking/session",
        TrackingViewSet.as_view({"post": "track_session"}),
        name="tracking-track-session-no-slash",
    ),
    path("", include(router.urls)),
]


