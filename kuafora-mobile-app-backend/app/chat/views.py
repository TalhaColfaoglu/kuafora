from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
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
            queryset = queryset.filter(customer=user)
            
        return queryset.order_by("-last_message_at")

    @action(detail=False, methods=["post"])
    def start(self, request):
        """Start or get existing room with a shop"""
        shop_id = request.data.get("shop_id")
        shop = get_object_or_404(Barbershop, id=shop_id)
        
        if ChatBan.objects.filter(barbershop=shop, user=request.user).exists():
            return Response({"detail": "You are banned from chatting with this shop."}, status=status.HTTP_403_FORBIDDEN)

        room, created = ChatRoom.objects.get_or_create(customer=request.user, barbershop=shop)
        return Response(ChatRoomSerializer(room).data)

    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        room = self.get_object()
        content = request.data.get("content")
        
        if ChatBan.objects.filter(barbershop=room.barbershop, user=room.customer).exists():
             return Response({"detail": "Chat banned."}, status=status.HTTP_403_FORBIDDEN)

        is_staff_reply = False
        # If user is staff of this shop, mark as staff reply
        if room.barbershop.staff.filter(user=request.user).exists():
            is_staff_reply = True
        elif room.customer != request.user:
             # If neither staff nor customer, forbid (unless admin?)
             return Response({"detail": "Not authorized"}, status=403)
        
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
        msgs = room.messages.all().order_by("created_at")
        return Response(ChatMessageSerializer(msgs, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def ban_user(self, request, pk=None):
        """Partner bans the user in this room"""
        room = self.get_object()
        # Check if request user is staff of this shop
        if not room.barbershop.staff.filter(user=request.user).exists():
            return Response({"detail": "Only shop staff can ban users"}, status=403)
            
        reason = request.data.get("reason", "Banned by shop")
        ChatBan.objects.create(barbershop=room.barbershop, user=room.customer, reason=reason)
        room.is_active = False
        room.save()
        return Response({"detail": "User banned"})

