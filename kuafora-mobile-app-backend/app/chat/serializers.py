from rest_framework import serializers
from .models import ChatRoom, ChatMessage

class ChatMessageSerializer(serializers.ModelSerializer):
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ("id", "room", "sender", "is_staff_reply", "content", "created_at", "read_at", "is_me")
        read_only_fields = ("id", "room", "sender", "created_at", "read_at", "is_me")

    def get_is_me(self, obj):
        request = self.context.get("request")
        if request and request.user:
            return obj.sender == request.user
        return False

class ChatRoomSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_image = serializers.SerializerMethodField()
    shop_name = serializers.CharField(source="barbershop.name", read_only=True)
    shop_image = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ("id", "customer", "customer_name", "customer_image", "barbershop", "shop_name", "shop_image", "is_active", "last_message_at", "last_message")
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return ChatMessageSerializer(last_msg).data
        return None

    def get_customer_image(self, obj):
        if obj.customer.image:
            return obj.customer.image.url
        return None

    def get_shop_image(self, obj):
        if obj.barbershop.main_image:
            return obj.barbershop.main_image.url
        return None

