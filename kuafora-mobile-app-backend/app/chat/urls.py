from rest_framework.routers import DefaultRouter
from .views import ChatRoomViewSet

router = DefaultRouter()
router.register(r"chat/rooms", ChatRoomViewSet, basename="chat-rooms")

urlpatterns = router.urls

