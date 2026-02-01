from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ChatRoom, ChatMessage
from app.barbers.models import Staff


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    is_me = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    sender_is_admin = serializers.SerializerMethodField()
    report_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = (
            "id", "room", "sender", "sender_name", "is_staff_reply", "sender_is_admin",
            "content", "created_at", "read_at", "is_hidden", "report_count",
            "is_me", "can_delete",
        )
        read_only_fields = ("sender", "created_at", "read_at", "is_staff_reply", "is_hidden")

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

    def get_can_delete(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if obj.sender == request.user:
            return True
        try:
            return obj.room.barbershop.staff.filter(user=request.user).exists()
        except Exception:
            return False

    def get_sender_is_admin(self, obj):
        """Gönderen bu kuaförde yetkili (admin) personel mi? UI'da farklı renk/badge için."""
        if not obj.is_staff_reply:
            return False
        try:
            staff = Staff.objects.filter(
                barbershop=obj.room.barbershop, user=obj.sender
            ).values_list("is_admin", flat=True).first()
            return staff is True
        except Exception:
            return False

    def get_report_count(self, obj):
        """Şikayet sayısı (personel/admin görsün). View'da annotate edilmiş olabilir."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        try:
            if obj.room.barbershop.staff.filter(user=request.user).exists():
                return getattr(obj, "report_count_annotated", None) or obj.reports.count()
        except Exception:
            pass
        return 0

class ChatRoomSerializer(serializers.ModelSerializer):
    # Backwards-compatible aliases
    barbershop_name = serializers.CharField(source='barbershop.name', read_only=True)
    barbershop_image = serializers.SerializerMethodField()

    # Mobile-app expected fields
    shop_name = serializers.CharField(source='barbershop.name', read_only=True)
    shop_image = serializers.SerializerMethodField()
    last_message_at = serializers.DateTimeField(read_only=True)
    unread_count = serializers.SerializerMethodField()
    can_moderate = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = (
            "id",
            "customer",
            "barbershop",
            "shop_name",
            "shop_image",
            "barbershop_name",
            "barbershop_image",
            "room_type",
            "is_public",
            "is_active",
            "last_message_at",
            "last_message",
            "unread_count",
            "can_moderate",
            "updated_at",
        )
        read_only_fields = ("customer", "is_active", "updated_at")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_barbershop_image(self, obj):
        if obj.barbershop.main_image_thumb:
            return obj.barbershop.main_image_thumb.url
        return None

    def get_shop_image(self, obj):
        return self.get_barbershop_image(obj)

    def get_unread_count(self, obj):
        # Not implemented yet (needs per-user read tracking).
        return 0

    def get_can_moderate(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        try:
            return obj.barbershop.staff.filter(user=request.user).exists()
        except Exception:
            return False
    
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_last_message(self, obj):
        request = self.context.get("request")
        qs = obj.messages.order_by("-created_at")
        if request and request.user.is_authenticated:
            try:
                if not obj.barbershop.staff.filter(user=request.user).exists():
                    qs = qs.filter(is_hidden=False)
            except Exception:
                pass
        last_msg = qs.first()
        if last_msg:
            return ChatMessageSerializer(last_msg, context=self.context).data
        return None
