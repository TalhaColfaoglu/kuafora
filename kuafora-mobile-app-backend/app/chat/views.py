from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import models
from .models import ChatRoom, ChatMessage, ChatBan
from .serializers import ChatRoomSerializer, ChatMessageSerializer
from app.barbers.models import Barbershop

class ChatRoomViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatRoomSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = ChatRoom.objects.all()
        
        if self.request.query_params.get("as_partner") == "true":
             staff_profiles = user.staff_profiles.all()
             shop_ids = staff_profiles.values_list("barbershop_id", flat=True)
             queryset = queryset.filter(barbershop__id__in=shop_ids)
        else:
            # Kullanıcı kendi özel odalarını ve katıldığı public odaları görebilir (public odalar için ek logic gerekebilir, şimdilik basitleştirilmiş)
            # Public rooms are theoretically visible to everyone, but typically accessed via start_public
            queryset = queryset.filter(
                models.Q(customer=user, room_type=ChatRoom.RoomType.PRIVATE) | 
                models.Q(room_type=ChatRoom.RoomType.PUBLIC)
            )
            
        return queryset.order_by("-last_message_at")

    @action(detail=False, methods=["post"])
    def start(self, request):
        """Start or get existing PRIVATE room with a shop"""
        shop_id = request.data.get("shop_id")
        shop = get_object_or_404(Barbershop, id=shop_id)
        
        if ChatBan.objects.filter(barbershop=shop, user=request.user).exists():
            return Response({"detail": "You are banned from chatting with this shop."}, status=status.HTTP_403_FORBIDDEN)

        room, created = ChatRoom.objects.get_or_create(
            customer=request.user, 
            barbershop=shop,
            room_type=ChatRoom.RoomType.PRIVATE
        )
        return Response(ChatRoomSerializer(room).data)

    @action(detail=False, methods=["post"])
    def start_public(self, request):
        """Start or get existing PUBLIC room for a shop"""
        shop_id = request.data.get("shop_id")
        shop = get_object_or_404(Barbershop, id=shop_id)
        
        if ChatBan.objects.filter(barbershop=shop, user=request.user).exists():
            return Response({"detail": "You are banned from chatting with this shop."}, status=status.HTTP_403_FORBIDDEN)

        # Public room is unique per shop
        room, created = ChatRoom.objects.get_or_create(
            barbershop=shop,
            room_type=ChatRoom.RoomType.PUBLIC,
            defaults={'customer': None}
        )
        return Response(ChatRoomSerializer(room).data)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        room = self.get_object()
        content = request.data.get("content")
        
        if not content or not content.strip():
            return Response({"detail": "Message content required"}, status=400)

        # Check ban status
        if request.user and ChatBan.objects.filter(barbershop=room.barbershop, user=request.user).exists():
             return Response({"detail": "Chat banned."}, status=status.HTTP_403_FORBIDDEN)

        is_staff_reply = False
        # If user is staff of this shop, mark as staff reply
        if room.barbershop.staff.filter(user=request.user).exists():
            is_staff_reply = True
        else:
            # Validation: if private room, user must be the customer
            if room.room_type == ChatRoom.RoomType.PRIVATE and room.customer != request.user:
                 return Response({"detail": "Not authorized"}, status=403)
            # Public room: anyone authenticated can write (except bans)
        
        msg = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content=content,
            is_staff_reply=is_staff_reply
        )
        room.last_message_at = msg.created_at
        room.save()
        
        return Response(ChatMessageSerializer(msg, context={"request": request}).data)
    
    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        room = self.get_object()
        
        # Access control for private rooms
        if room.room_type == ChatRoom.RoomType.PRIVATE:
            is_staff = room.barbershop.staff.filter(user=request.user).exists()
            if room.customer != request.user and not is_staff:
                return Response({"detail": "Not authorized"}, status=403)
        
        msgs = room.messages.all().select_related('sender').order_by("created_at")
        return Response(ChatMessageSerializer(msgs, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def ban_user(self, request, pk=None):
        """Partner bans the user in this room"""
        room = self.get_object()
        # Check if request user is staff of this shop
        if not room.barbershop.staff.filter(user=request.user).exists():
            return Response({"detail": "Only shop staff can ban users"}, status=403)
            
        # For private room, ban the customer
        target_user = None
        if room.room_type == ChatRoom.RoomType.PRIVATE:
            target_user = room.customer
        else:
            # For public room, we need target_user_id in request
            target_user_id = request.data.get("user_id")
            if not target_user_id:
                return Response({"detail": "User ID required for public ban"}, status=400)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target_user = get_object_or_404(User, id=target_user_id)

        reason = request.data.get("reason", "Banned by shop")
        ChatBan.objects.create(barbershop=room.barbershop, user=target_user, reason=reason)
        
        if room.room_type == ChatRoom.RoomType.PRIVATE:
            room.is_active = False
            room.save()
            
        return Response({"detail": "User banned"})
