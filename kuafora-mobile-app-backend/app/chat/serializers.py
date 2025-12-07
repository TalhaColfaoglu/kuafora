from rest_framework import serializers
from .models import ChatRoom, ChatMessage

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ("id", "room", "sender", "sender_name", "is_staff_reply", "content", "created_at", "read_at", "is_me")
        read_only_fields = ("sender", "created_at", "read_at", "is_staff_reply")

    def get_is_me(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.sender == request.user
        return False

    def get_sender_name(self, obj):
        # If room is public, mask the name
        if obj.room.is_public:
            # Check if sender is staff of that barbershop
            is_staff = obj.is_staff_reply
            if is_staff:
                return obj.room.barbershop.name
            
            # Mask user name: "Ahmet Yılmaz" -> "Ahmet Y."
            full_name = getattr(obj.sender, "full_name", "") or f"{getattr(obj.sender, 'first_name', '')} {getattr(obj.sender, 'last_name', '')}".strip()
            if not full_name:
                return "Kullanıcı"
            
            parts = full_name.split()
            if len(parts) > 1:
                return f"{parts[0]} {parts[-1][0]}."
            return full_name

        # Private room logic
        return getattr(obj.sender, "full_name", "Kullanıcı")

from drf_spectacular.utils import extend_schema_field

class ChatRoomSerializer(serializers.ModelSerializer):
    barbershop_name = serializers.CharField(source='barbershop.name', read_only=True)
    barbershop_image = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ("id", "customer", "barbershop", "barbershop_name", "barbershop_image", "room_type", "is_public", "is_active", "last_message", "updated_at")
        read_only_fields = ("customer", "is_active", "updated_at")

    @extend_schema_field(serializers.CharField)
    def get_barbershop_image(self, obj):
        if obj.barbershop.main_image_thumb:
            return obj.barbershop.main_image_thumb.url
        return None
    
    @extend_schema_field(serializers.DictField)
    def get_last_message(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if last_msg:
            return ChatMessageSerializer(last_msg, context=self.context).data
        return None
