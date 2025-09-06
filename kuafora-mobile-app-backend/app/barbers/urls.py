from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FavoriteListView,
    FavoriteToggleView,
    BarbershopViewSet,
    ReviewViewSet,
    ReviewUpsertApi,
    ReviewHighlightsApi,
    BarbershopReviewsListApi,
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
    # Koruma: hem ViewSet action hem de ayrı list api mevcut; upsert da ayrıca açık
    path("barbershops/<int:barber_id>/reviews/upsert/", ReviewUpsertApi.as_view(), name="barber-review-upsert"),
    path("barbershops/<int:barber_id>/reviews/highlights/", ReviewHighlightsApi.as_view(), name="barber-review-highlights"),
    # ViewSet action için router zaten /barbershops/{id}/reviews/ sağlıyor; ekstra list api de mevcut
    path("barbershops/<int:barber_id>/reviews/", BarbershopReviewsListApi.as_view(), name="barber-review-list"),
    path("", include(router.urls)),
    path("favorites/", FavoriteListView.as_view(), name="favorites-list"),
    path("favorites/toggle/<int:barbershop_id>/", FavoriteToggleView.as_view(), name="favorites-toggle"),
]
