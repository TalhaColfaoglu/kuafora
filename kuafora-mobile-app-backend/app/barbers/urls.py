from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BarbershopViewSet,
    ReviewViewSet,
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
    path("", include(router.urls)),
]


