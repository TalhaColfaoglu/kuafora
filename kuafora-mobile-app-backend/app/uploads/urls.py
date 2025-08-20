from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UploadedImageViewSet

router = DefaultRouter()
router.register(r"uploads/images", UploadedImageViewSet, basename="uploads-images")

urlpatterns = [
    path("", include(router.urls)),
]


