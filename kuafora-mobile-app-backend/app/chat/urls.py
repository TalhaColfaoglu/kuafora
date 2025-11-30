from rest_framework.routers import DefaultRouter
from .views import ChatRoomViewSet, ChatBanViewSet

router = DefaultRouter()
router.register(r"chat/rooms", ChatRoomViewSet, basename="chat-rooms")
router.register(r"chat/bans", ChatBanViewSet, basename="chat-bans")

urlpatterns = router.urls

