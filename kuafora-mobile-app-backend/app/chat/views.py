from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import ChatRoom, ChatMessage, ChatBan, ChatMessageReport
from .serializers import ChatRoomSerializer, ChatMessageSerializer
from app.barbers.models import Barbershop

# Mesaj uzunluk ve spam limitleri
CHAT_MESSAGE_MAX_LENGTH = 200
CHAT_MESSAGE_RATE_WINDOW_SECONDS = 30
CHAT_MESSAGE_RATE_MAX_PER_WINDOW = 5
CHAT_REPORT_AUTO_HIDE_THRESHOLD = 3

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
        content = (request.data.get("content") or "").strip()

        if not content:
            return Response({"detail": "Mesaj içeriği gerekli."}, status=status.HTTP_400_BAD_REQUEST)
        if len(content) > CHAT_MESSAGE_MAX_LENGTH:
            return Response(
                {"detail": f"Mesaj en fazla {CHAT_MESSAGE_MAX_LENGTH} karakter olabilir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check ban status
        if request.user and ChatBan.objects.filter(barbershop=room.barbershop, user=request.user).exists():
            return Response({"detail": "Bu kuaförle sohbet edemezsiniz (engellendiniz)."}, status=status.HTTP_403_FORBIDDEN)

        is_staff = room.barbershop.staff.filter(user=request.user).exists()
        if not is_staff:
            # Spam: son X saniyede bu odada bu kullanıcının mesaj sayısı
            since = timezone.now() - timedelta(seconds=CHAT_MESSAGE_RATE_WINDOW_SECONDS)
            recent_count = ChatMessage.objects.filter(
                room=room, sender=request.user, created_at__gte=since
            ).count()
            if recent_count >= CHAT_MESSAGE_RATE_MAX_PER_WINDOW:
                return Response(
                    {"detail": "Çok hızlı mesaj gönderiyorsunuz. Lütfen biraz bekleyin."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            if room.room_type == ChatRoom.RoomType.PRIVATE and room.customer != request.user:
                return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        msg = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content=content,
            is_staff_reply=is_staff,
        )
        room.last_message_at = msg.created_at
        room.save(update_fields=["last_message_at", "updated_at"])
        return Response(ChatMessageSerializer(msg, context={"request": request}).data)
    
    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        room = self.get_object()
        is_staff = room.barbershop.staff.filter(user=request.user).exists()
        if room.room_type == ChatRoom.RoomType.PRIVATE:
            if room.customer != request.user and not is_staff:
                return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        msgs = room.messages.all().select_related("sender").order_by("created_at")
        if not is_staff:
            msgs = msgs.filter(is_hidden=False)
        else:
            msgs = msgs.annotate(report_count_annotated=Count("reports"))
        return Response(
            ChatMessageSerializer(msgs, many=True, context={"request": request}).data
        )

    @action(detail=True, methods=["post"], url_path="report_message")
    def report_message(self, request, pk=None):
        """Mesaja şikayet et. 3 farklı kullanıcı şikayet edince mesaj otomatik gizlenir."""
        room = self.get_object()
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id gerekli."}, status=status.HTTP_400_BAD_REQUEST)
        msg = get_object_or_404(ChatMessage, id=message_id, room=room)
        if msg.sender_id == request.user.id:
            return Response({"detail": "Kendi mesajınızı şikayet edemezsiniz."}, status=status.HTTP_400_BAD_REQUEST)
        if msg.is_hidden:
            return Response({"detail": "Bu mesaj zaten gizlendi."}, status=status.HTTP_400_BAD_REQUEST)

        report, created = ChatMessageReport.objects.get_or_create(
            message=msg, user=request.user, defaults={}
        )
        if not created:
            return Response({"detail": "Bu mesajı zaten şikayet ettiniz."}, status=status.HTTP_400_BAD_REQUEST)

        count = msg.reports.count()
        if count >= CHAT_REPORT_AUTO_HIDE_THRESHOLD:
            msg.is_hidden = True
            msg.hidden_at = timezone.now()
            msg.save(update_fields=["is_hidden", "hidden_at"])
        return Response({"detail": "Şikayetiniz alındı.", "hidden": count >= CHAT_REPORT_AUTO_HIDE_THRESHOLD})

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

    @action(detail=True, methods=["post"], url_path=r"messages/(?P<message_id>[^/.]+)/unhide")
    def unhide_message(self, request, pk=None, message_id=None):
        """Personel: 3 şikayet sonrası gizlenen mesajı tekrar görünür yapar."""
        room = self.get_object()
        if not room.barbershop.staff.filter(user=request.user).exists():
            return Response({"detail": "Sadece kuaför personeli mesajı görünür yapabilir."}, status=status.HTTP_403_FORBIDDEN)
        msg = get_object_or_404(ChatMessage, id=message_id, room=room)
        if not msg.is_hidden:
            return Response({"detail": "Bu mesaj zaten görünür."}, status=status.HTTP_400_BAD_REQUEST)
        msg.is_hidden = False
        msg.hidden_at = None
        msg.save(update_fields=["is_hidden", "hidden_at"])
        return Response(ChatMessageSerializer(msg, context={"request": request}).data)

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
