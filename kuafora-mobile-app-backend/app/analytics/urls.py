from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.analytics.views import TrackingViewSet, AnalyticsViewSet

router = DefaultRouter()
router.register(r'tracking', TrackingViewSet, basename='tracking')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    path('', include(router.urls)),
]

