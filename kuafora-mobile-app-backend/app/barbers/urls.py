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
    PartnerServiceViewSetSecure,
    PartnerServiceCategoryViewSet,
    PartnerStaffViewSet,
    StaffServiceViewSet,
    StaffServiceCategoryViewSet,
    PartnerWorkScheduleViewSet,
    ReviewReplyViewSet,
    LastViewedViewSet,
    PartnerShopWorkingHoursViewSet,
    PartnerStaffWorkingHoursViewSet,
    PartnerOverrideViewSet,
    PartnerSpecialMessageViewSet,
    CalendarStatusViewSet,
    AnnouncementsPublicApi,
    PartnerHolidayOverrideViewSet,
)

router = DefaultRouter()
router.register(r"barbershops", BarbershopViewSet, basename="barbershop")
router.register(r"last-viewed", LastViewedViewSet, basename="last-viewed")
router.register(r"reviews", ReviewViewSet, basename="review")

router.register(r"partner/barbershops", PartnerBarbershopViewSet, basename="partner-barbershop")
# Kategori route'unu, service route'u ile çakışmayı önlemek için ayrı prefix ile tanımla
router.register(r"partner/service-categories", PartnerServiceCategoryViewSet, basename="partner-service-category")
router.register(r"partner/services", PartnerServiceViewSetSecure, basename="partner-service")
router.register(r"partner/staff", PartnerStaffViewSet, basename="partner-staff")
router.register(r"partner/staff-services", StaffServiceViewSet, basename="partner-staff-services")
router.register(r"partner/staff-categories", StaffServiceCategoryViewSet, basename="partner-staff-categories")
router.register(r"partner/working-hours", PartnerWorkScheduleViewSet, basename="partner-work-schedule")
router.register(r"partner/review-replies", ReviewReplyViewSet, basename="partner-review-reply")
router.register(r"partner/shop-working-hours", PartnerShopWorkingHoursViewSet, basename="partner-shop-working-hours")
router.register(r"partner/staff-working-hours", PartnerStaffWorkingHoursViewSet, basename="partner-staff-working-hours")
router.register(r"partner/overrides", PartnerOverrideViewSet, basename="partner-override")
router.register(r"partner/special-messages", PartnerSpecialMessageViewSet, basename="partner-special-message")
router.register(r"partner/holidayoverride", PartnerHolidayOverrideViewSet, basename="partner-holiday-override")
router.register(r"calendar", CalendarStatusViewSet, basename="calendar-status")

urlpatterns = [
    # Koruma: hem ViewSet action hem de ayrı list api mevcut; upsert da ayrıca açık
    path("barbershops/<int:barber_id>/reviews/upsert/", ReviewUpsertApi.as_view(), name="barber-review-upsert"),
    path("barbershops/<int:barber_id>/reviews/highlights/", ReviewHighlightsApi.as_view(), name="barber-review-highlights"),
    # ViewSet action için router zaten /barbershops/{id}/reviews/ sağlıyor; ekstra list api de mevcut
    path("barbershops/<int:barber_id>/reviews/", BarbershopReviewsListApi.as_view(), name="barber-review-list"),
    path("", include(router.urls)),
    path("favorites/", FavoriteListView.as_view(), name="favorites-list"),
    path("favorites/toggle/<int:barbershop_id>/", FavoriteToggleView.as_view(), name="favorites-toggle"),
    # Public announcements for mobile app
    path("announcements/", AnnouncementsPublicApi.as_view(), name="announcements-public"),
    path("special-messages/", AnnouncementsPublicApi.as_view(), name="special-messages-public"),
]
