from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FavoriteListView,
    FavoriteToggleView,
    BarbershopViewSet,
    ReviewViewSet,
    ReviewUpsertApi,
    ReviewHighlightsApi,
    PartnerBarbershopViewSet,
    PartnerServiceViewSet,
    PartnerStaffViewSet,
    PartnerWorkScheduleViewSet,
    LastViewedViewSet,
)

router = DefaultRouter()
router.register(r"barbershops", BarbershopViewSet, basename="barbershop")
router.register(r"last-viewed", LastViewedViewSet, basename="last-viewed")
router.register(r"reviews", ReviewViewSet, basename="review")

router.register(r"partner/barbershops", PartnerBarbershopViewSet, basename="partner-barbershop")
router.register(r"partner/services", PartnerServiceViewSet, basename="partner-service")
router.register(r"partner/staff", PartnerStaffViewSet, basename="partner-staff")
router.register(r"partner/working-hours", PartnerWorkScheduleViewSet, basename="partner-work-schedule")

urlpatterns = [
    # Upsert endpointi ayrı path'e alındı ki GET /barbershops/{id}/reviews/ ViewSet'e düşsün
    path("barbershops/<int:barber_id>/reviews/upsert/", ReviewUpsertApi.as_view(), name="barber-review-upsert"),
    path("barbershops/<int:barber_id>/reviews/highlights/", ReviewHighlightsApi.as_view(), name="barber-review-highlights"),
    path("", include(router.urls)),
    path("favorites/", FavoriteListView.as_view(), name="favorites-list"),
    path("favorites/toggle/<int:barbershop_id>/", FavoriteToggleView.as_view(), name="favorites-toggle"),
]
