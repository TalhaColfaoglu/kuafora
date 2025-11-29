from rest_framework import viewsets, permissions
from django.utils import timezone
from app.barbers.models import Staff
from .models import Campaign
from .serializers import CampaignSerializer, CampaignCreateSerializer

class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CampaignCreateSerializer
        return CampaignSerializer

    def get_queryset(self):
        # Only return campaigns for the shop the staff belongs to
        try:
            staff = Staff.objects.filter(user=self.request.user).first()
            if not staff:
                return Campaign.objects.none()
            return Campaign.objects.filter(barbershop=staff.barbershop).order_by("-created_at")
        except Exception:
            return Campaign.objects.none()

    def perform_create(self, serializer):
        staff = Staff.objects.filter(user=self.request.user).first()
        if staff:
            serializer.save(barbershop=staff.barbershop)

class PublicCampaignViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = CampaignSerializer
    
    def get_queryset(self):
        shop_id = self.request.query_params.get("shop_id")
        if not shop_id:
            return Campaign.objects.none()
        
        today = timezone.now().date()
        return Campaign.objects.filter(
            barbershop_id=shop_id,
            is_active=True,
            end_date__gte=today,
            start_date__lte=today
        ).order_by("-created_at")

