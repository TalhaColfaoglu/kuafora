from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.utils import timezone
from datetime import timedelta
from .models import Barbershop, ShopCategory
from .home_serializers import ShopCategorySerializer, BarbershopHomeSerializer
from app.campaigns.models import Campaign

class HomeDashboardApi(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        city = request.query_params.get('city')
        
        # 1. Categories
        categories = ShopCategory.objects.filter(is_active=True)
        cat_data = ShopCategorySerializer(categories, many=True).data

        # Base query for shops
        shops_qs = Barbershop.objects.all()
        if city:
            shops_qs = shops_qs.filter(city__icontains=city)

        # 2. Newest (last 60 days)
        sixty_days_ago = timezone.now() - timedelta(days=60)
        newest = shops_qs.filter(created_at__gte=sixty_days_ago).order_by('-created_at')[:10]
        newest_data = BarbershopHomeSerializer(newest, many=True).data

        # 3. Top Rated
        top_rated = shops_qs.filter(rating_avg__gte=4.5).order_by('-rating_avg')[:10]
        top_rated_data = BarbershopHomeSerializer(top_rated, many=True).data

        # 4. Campaigns
        today = timezone.now().date()
        active_campaigns = Campaign.objects.filter(
            is_active=True, 
            start_date__lte=today, 
            end_date__gte=today
        ).select_related('barbershop')
        
        if city:
            active_campaigns = active_campaigns.filter(barbershop__city__icontains=city)

        campaign_data = []
        for c in active_campaigns[:10]:
            campaign_data.append({
                "id": c.id,
                "title": c.name,
                "type": c.type,
                "shop_id": c.barbershop.id,
                "shop_name": c.barbershop.name,
                "discount_value": c.discount_value,
                "discount_type": c.discount_type,
                "image": c.barbershop.main_image.url if c.barbershop.main_image else None
            })

        return Response({
            "categories": cat_data,
            "newest_shops": newest_data,
            "top_rated_shops": top_rated_data,
            "campaigns": campaign_data
        })

