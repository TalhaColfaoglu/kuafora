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
    PartnerReviewViewSet,
    LastViewedViewSet,
    TrackViewApi,
    PartnerShopWorkingHoursViewSet,
    PartnerStaffWorkingHoursViewSet,
    PartnerBreakWindowViewSet,
    PartnerOverrideViewSet,
    PartnerSpecialMessageViewSet,
    CalendarStatusViewSet,
    ToggleTodayApi,
    AnnouncementsPublicApi,
    PartnerHolidayOverrideViewSet,
    ImpactPlusApi,
    ShopCategoryViewSet,
)
from app.subscriptions.views import SubscriptionViewSet
from .home_views import HomeDashboardApi
from .stats_views import BarbershopAdvancedStatsView

router = DefaultRouter()
router.register(r"barbershops", BarbershopViewSet, basename="barbershop")
router.register(r"last-viewed", LastViewedViewSet, basename="last-viewed")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"shop-categories", ShopCategoryViewSet, basename="shop-category")

router.register(r"partner/barbershops", PartnerBarbershopViewSet, basename="partner-barbershop")
# Kategori route'unu, service route'u ile çakışmayı önlemek için ayrı prefix ile tanımla
router.register(r"partner/service-categories", PartnerServiceCategoryViewSet, basename="partner-service-category")
router.register(r"partner/services", PartnerServiceViewSetSecure, basename="partner-service")
router.register(r"partner/staff", PartnerStaffViewSet, basename="partner-staff")
router.register(r"partner/staff-services", StaffServiceViewSet, basename="partner-staff-services")
router.register(r"partner/staff-categories", StaffServiceCategoryViewSet, basename="partner-staff-categories")
router.register(r"partner/working-hours", PartnerWorkScheduleViewSet, basename="partner-work-schedule")
router.register(r"partner/review-replies", ReviewReplyViewSet, basename="partner-review-reply")
router.register(r"partner/reviews", PartnerReviewViewSet, basename="partner-reviews")
router.register(r"partner/shop-working-hours", PartnerShopWorkingHoursViewSet, basename="partner-shop-working-hours")
router.register(r"partner/staff-working-hours", PartnerStaffWorkingHoursViewSet, basename="partner-staff-working-hours")
router.register(r"partner/break-windows", PartnerBreakWindowViewSet, basename="partner-break-window")
router.register(r"partner/overrides", PartnerOverrideViewSet, basename="partner-override")
router.register(r"partner/special-messages", PartnerSpecialMessageViewSet, basename="partner-special-message")
router.register(r"partner/holidayoverride", PartnerHolidayOverrideViewSet, basename="partner-holiday-override")
router.register(r"calendar", CalendarStatusViewSet, basename="calendar-status")

urlpatterns = [
    # Router'ı önce include et ki ViewSet action'ları çalışsın
    path("", include(router.urls)),
    
    # Robust toggle endpoints (avoid router clashes)
    path("toggle-today/", ToggleTodayApi.as_view(), name="toggle-today"),
    path("calendar/toggle/", ToggleTodayApi.as_view(), name="calendar-toggle"),
    path("barbershops/today-toggle/", ToggleTodayApi.as_view(), name="barbershops-today-toggle"),
    path("barbershops/<int:barbershop_id>/toggle/", ToggleTodayApi.as_view(), name="barbershops-toggle-by-id"),

    # Koruma: hem ViewSet action hem de ayrı list api mevcut; upsert da ayrıca açık
    path("barbershops/<int:barber_id>/reviews/upsert/", ReviewUpsertApi.as_view(), name="barber-review-upsert"),
    path("barbershops/<int:barber_id>/reviews/highlights/", ReviewHighlightsApi.as_view(), name="barber-review-highlights"),
    # ViewSet action için router zaten /barbershops/{id}/reviews/ sağlıyor; ekstra list api de mevcut (sadece GET için)
    path("barbershops/<int:barber_id>/reviews/", BarbershopReviewsListApi.as_view(), name="barber-review-list"),
    
    # Manual overrides for Partner Reviews to ensure 404 is resolved
    path("partner/reviews/", PartnerReviewViewSet.as_view({'get': 'list'}), name="partner-reviews-list-manual"),
    path("partner/reviews/<int:pk>/", PartnerReviewViewSet.as_view({'get': 'retrieve'}), name="partner-reviews-detail-manual"),
    path("partner/reviews/<int:pk>/reply/", PartnerReviewViewSet.as_view({'post': 'reply'}), name="partner-reviews-reply-manual"),
    path("favorites/", FavoriteListView.as_view(), name="favorites-list"),
    path("favorites/toggle/<int:barbershop_id>/", FavoriteToggleView.as_view(), name="favorites-toggle"),
    # Public announcements for mobile app
    path("announcements/", AnnouncementsPublicApi.as_view(), name="announcements-public"),
    path("special-messages/", AnnouncementsPublicApi.as_view(), name="special-messages-public"),
    # Track view - Hem misafir hem giriş yapmış kullanıcılar için görüntülenme takibi
    path("track-view/", TrackViewApi.as_view(), name="track-view"),
    # Impact plus
    path("partner/holiday/impact-plus/", ImpactPlusApi.as_view(), name="impact-plus"),
    path("mobile/home/dashboard/", HomeDashboardApi.as_view(), name="mobile-home-dashboard"),
    # Advanced Stats
    path("partner/stats/advanced/", BarbershopAdvancedStatsView.as_view(), name="partner-stats-advanced"),
    # Subscription aliases (must be here because barbers.urls is included before subscriptions.urls)
    path(
        "partner/subscriptions/my_subscription/",
        SubscriptionViewSet.as_view({"get": "my_subscription"}),
        name="partner-subscriptions-my-subscription",
    ),
    path(
        "partner/subscriptions/start-trial/",
        SubscriptionViewSet.as_view({"post": "start_trial"}),
        name="partner-subscriptions-start-trial",
    ),
    path(
        "partner/subscriptions/apply-coupon/",
        SubscriptionViewSet.as_view({"post": "apply_coupon"}),
        name="partner-subscriptions-apply-coupon",
    ),
    
    # Calendar aliases for APPEND_SLASH=False compatibility
    path("calendar/holidays", CalendarStatusViewSet.as_view({'get': 'holidays'}), name="calendar-holidays-alias"),
    path("calendar/now", CalendarStatusViewSet.as_view({'get': 'now'}), name="calendar-now-alias"),
    # Official holidays alias for APPEND_SLASH=False compatibility
    path("partner/holidayoverride/official-holidays", PartnerHolidayOverrideViewSet.as_view({'get': 'official_holidays'}), name="partner-holiday-override-official-holidays-alias"),
]
