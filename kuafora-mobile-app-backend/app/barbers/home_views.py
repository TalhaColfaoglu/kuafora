from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.utils import timezone
from datetime import timedelta
from .models import Barbershop, ShopCategory
from .home_serializers import ShopCategorySerializer, BarbershopHomeSerializer
from app.campaigns.models import Campaign
from .views import BarbershopViewSet

class HomeDashboardApi(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = None

    def get(self, request):
        city = request.query_params.get('city')
        
        # 1. Categories
        categories = ShopCategory.objects.filter(is_active=True)
        cat_data = ShopCategorySerializer(categories, many=True).data

        # Base query for shops - Sadece aktif subscription'ı olanlar, ismi olanlar ve banlı olmayanlar
        from app.subscriptions.models import Subscription
        shops_qs = Barbershop.objects.filter(
            subscription__status__in=['trial', 'active', 'lifetime', 'grace_period'],
            name__isnull=False,
            is_verified=True  # Banlı kuaförleri filtrele
        ).exclude(name='')
        if city:
            shops_qs = shops_qs.filter(city__icontains=city)

        # 2. Newest (last 60 days) - İsimsiz kuaförleri filtrele
        sixty_days_ago = timezone.now() - timedelta(days=60)
        newest = list(shops_qs.filter(created_at__gte=sixty_days_ago).order_by('-created_at')[:10])

        # 3. Top Rated - İsimsiz kuaförleri filtrele
        top_rated = list(shops_qs.filter(rating_avg__gte=4.5).order_by('-rating_avg')[:10])

        # Entegre açık/kapalı ve cinsiyet bilgisi
        serializer = BarbershopHomeSerializer()
        status_helper = BarbershopViewSet()
        now_utc = timezone.now()
        now_local = timezone.localtime(now_utc)
        today = now_local.date()
        current_time = now_local.time()

        def serialize_shop(shop: Barbershop):
          base = serializer.to_representation(shop)
          try:
              status = status_helper._calculate_shop_status(shop, today)  # type: ignore[attr-defined]
              is_open_today = bool(status.get("is_open"))
              
              # Eğer bugün açıksa, şu anki saatte açık mı kontrol et
              if is_open_today:
                  opening_time = status.get("opening_time")
                  closing_time = status.get("closing_time")
                  if opening_time and closing_time:
                      # Eğer açılış saati kapanış saatinden büyükse (gece yarısını geçiyorsa)
                      if opening_time > closing_time:
                          # Gece yarısından sonra açılıyorsa (örn: 22:00 - 02:00)
                          is_open = current_time >= opening_time or current_time <= closing_time
                      else:
                          # Normal saat aralığı (örn: 09:00 - 18:00)
                          is_open = opening_time <= current_time <= closing_time
                  else:
                      is_open = True  # Saat bilgisi yoksa açık kabul et
              else:
                  is_open = False
              
              base["is_open"] = is_open
          except Exception:
              base["is_open"] = False  # Hata durumunda kapalı göster
          base["gender"] = getattr(shop, "gender", "unisex")
          return base

        newest_data = [serialize_shop(s) for s in newest]
        top_rated_data = [serialize_shop(s) for s in top_rated]

        # 4. Campaigns - Sadece aktif subscription'ı olan ve banlı olmayan barbershop'ların kampanyaları
        from app.subscriptions.models import Subscription
        active_campaigns = Campaign.objects.filter(
            is_active=True, 
            start_date__lte=today, 
            end_date__gte=today,
            barbershop__subscription__status__in=['trial', 'active', 'lifetime', 'grace_period'],
            barbershop__is_verified=True  # Banlı kuaförlerin kampanyalarını filtrele
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

