from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q
from .models import ChatRoom, ChatMessage, ChatBan
from .serializers import ChatRoomSerializer, ChatMessageSerializer
from app.barbers.models import Barbershop

class ChatRoomViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatRoomSerializer

    def get_queryset(self):
        # Schema jenerasyonu veya anonim kullanıcıda güvenli boş queryset
        if getattr(self, "swagger_fake_view", False) or not self.request or self.request.user.is_anonymous:
            return ChatRoom.objects.none()

        user = self.request.user
        queryset = ChatRoom.objects.all()

        as_partner = self.request.query_params.get("as_partner") == "true"

        # If the user is a staff member of any shop, allow access to those shops' rooms as well.
        staff_profiles = getattr(user, "staff_profiles", None)
        shop_ids = []
        if staff_profiles is not None:
            shop_ids = list(staff_profiles.all().values_list("barbershop_id", flat=True))

        if as_partner:
            # Partner-side listing: only rooms for staff's shops
            if not shop_ids:
                return ChatRoom.objects.none()
            return queryset.filter(barbershop__id__in=shop_ids).order_by("-last_message_at")

        # Default: customer rooms + public rooms + (if staff) their shop rooms
        q = Q(room_type=ChatRoom.RoomType.PUBLIC) | Q(customer=user, room_type=ChatRoom.RoomType.PRIVATE)
        if shop_ids:
            q |= Q(barbershop__id__in=shop_ids)
        return queryset.filter(q).order_by("-last_message_at")

    @action(detail=False, methods=["post"])
    def start(self, request):
        """Start or get existing PRIVATE room with a shop"""
        shop_id = request.data.get("shop_id")
        shop = get_object_or_404(Barbershop, id=shop_id)
        
        if ChatBan.objects.filter(barbershop=shop, user=request.user).exists():
            return Response({"detail": "You are banned from chatting with this shop."}, status=status.HTTP_403_FORBIDDEN)

        # IMPORTANT: Without a DB uniqueness constraint, duplicates can happen (race conditions / legacy data),
        # which leads to split conversations (customer sees only their own messages). Canonicalize on access.
        rooms = ChatRoom.objects.filter(
            customer=request.user,
            barbershop=shop,
            room_type=ChatRoom.RoomType.PRIVATE,
        ).order_by("created_at", "id")

        if rooms.exists():
            room = rooms.first()
            dupes = rooms.exclude(id=room.id)
            if dupes.exists():
                # Move messages into the canonical room, then remove duplicates.
                ChatMessage.objects.filter(room__in=dupes).update(room=room)
                dupes.delete()
            return Response(ChatRoomSerializer(room, context={"request": request}).data)

        room = ChatRoom.objects.create(
            customer=request.user,
            barbershop=shop,
            room_type=ChatRoom.RoomType.PRIVATE,
        )
        return Response(ChatRoomSerializer(room, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def start_public(self, request):
        """Start or get existing PUBLIC room for a shop"""
        shop_id = request.data.get("shop_id")
        shop = get_object_or_404(Barbershop, id=shop_id)
        
        if ChatBan.objects.filter(barbershop=shop, user=request.user).exists():
            return Response({"detail": "You are banned from chatting with this shop."}, status=status.HTTP_403_FORBIDDEN)

        # Public room should be unique per shop. Canonicalize duplicates if any exist.
        rooms = ChatRoom.objects.filter(
            barbershop=shop,
            room_type=ChatRoom.RoomType.PUBLIC,
        ).order_by("created_at", "id")

        if rooms.exists():
            room = rooms.first()
            # Ensure public room has no customer bound.
            if room.customer_id is not None:
                room.customer = None
                room.save(update_fields=["customer", "updated_at"])

            dupes = rooms.exclude(id=room.id)
            if dupes.exists():
                ChatMessage.objects.filter(room__in=dupes).update(room=room)
                dupes.delete()
            return Response(ChatRoomSerializer(room, context={"request": request}).data)

        room = ChatRoom.objects.create(
            barbershop=shop,
            room_type=ChatRoom.RoomType.PUBLIC,
            customer=None,
            is_public=True,
        )
        return Response(ChatRoomSerializer(room, context={"request": request}).data)

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

    @action(detail=True, methods=["delete"], url_path=r"messages/(?P<message_id>[^/.]+)")
    def delete_message(self, request, pk=None, message_id=None):
        room = self.get_object()

        # Re-use the same access control as "messages"
        if room.room_type == ChatRoom.RoomType.PRIVATE:
            is_staff = room.barbershop.staff.filter(user=request.user).exists()
            if room.customer != request.user and not is_staff:
                return Response({"detail": "Not authorized"}, status=403)

        msg = get_object_or_404(ChatMessage, id=message_id, room=room)

        is_staff = room.barbershop.staff.filter(user=request.user).exists()
        is_sender = msg.sender_id == request.user.id
        if not is_staff and not is_sender:
            return Response({"detail": "Not authorized"}, status=403)

        msg.delete()

        # Keep room.last_message_at consistent
        last = room.messages.order_by("-created_at").first()
        room.last_message_at = last.created_at if last else room.created_at
        room.save(update_fields=["last_message_at", "updated_at"])

        return Response({"success": True}, status=status.HTTP_200_OK)

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
