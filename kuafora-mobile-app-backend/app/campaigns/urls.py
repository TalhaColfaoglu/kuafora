from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet, PublicCampaignViewSet

router = DefaultRouter()
router.register(r'partner/campaigns', CampaignViewSet, basename='partner-campaign')
router.register(r'public/campaigns', PublicCampaignViewSet, basename='public-campaign')

urlpatterns = [
    path('', include(router.urls)),
]

