from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.core.cache import cache
import hashlib
import math
from .models import Barbershop, ShopCategory
from .home_serializers import ShopCategorySerializer, BarbershopHomeSerializer
from app.campaigns.models import Campaign
from .views import BarbershopViewSet

class HomeDashboardApi(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = None

    def get(self, request):
        # Cache key oluştur - query parametrelerine göre
        city = request.query_params.get('city', '')
        lat = request.query_params.get('lat', '')
        lng = request.query_params.get('lng', '')
        radius_km = request.query_params.get('radius_km', '10')
        
        # Cache key için hash oluştur
        cache_params = f"{city}_{lat}_{lng}_{radius_km}"
        cache_key = f"home_dashboard_{hashlib.md5(cache_params.encode()).hexdigest()}"
        
        # Cache'den kontrol et (2 dakika TTL)
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)
        
        # Convert radius_km to float for calculations
        try:
            radius_km = float(radius_km) if radius_km else 10.0
        except (ValueError, TypeError):
            radius_km = 10.0
        
        # 1. Categories
        categories = ShopCategory.objects.filter(is_active=True)
        cat_data = ShopCategorySerializer(categories, many=True).data

        # Base query for shops - Sadece aktif subscription'ı olanlar, ismi olanlar ve banlı olmayanlar
        # Performance: select_related ve prefetch_related ile optimize et
        from app.subscriptions.models import Subscription
        shops_qs = Barbershop.objects.filter(
            subscription__status__in=['trial', 'active', 'lifetime', 'grace_period'],
            name__isnull=False,
            is_verified=True,  # Banlı kuaförleri filtrele
            is_approved=True  # Admin onayı - sadece onaylanmış kuaförler ana uygulamada görünür
        ).exclude(name='').select_related('subscription').prefetch_related('images', 'categories')

        if city:
            shops_qs = shops_qs.filter(city__icontains=city)

        # Konuma göre öneriler: 10km yarıçap filtre (basit bounding box)
        if lat and lng:
            try:
                lat_v = float(lat)
                lng_v = float(lng)
                lat_delta = radius_km / 110.0
                # longitude delta: 111km * cos(lat)
                lng_delta = radius_km / (111.0 * max(abs(math.cos(math.radians(lat_v))), 0.2))
                shops_qs = shops_qs.filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                    latitude__gte=lat_v - lat_delta,
                    latitude__lte=lat_v + lat_delta,
                    longitude__gte=lng_v - lng_delta,
                    longitude__lte=lng_v + lng_delta,
                )
            except (ValueError, TypeError):
                pass

        # 2. Newest (last 60 days) - İsimsiz kuaförleri filtrele
        sixty_days_ago = timezone.now() - timedelta(days=60)
        newest = list(shops_qs.filter(created_at__gte=sixty_days_ago).order_by('-created_at')[:10])

        # 3. Top Rated - İsimsiz kuaförleri filtrele
        top_rated = list(shops_qs.filter(rating_avg__gte=4.5).order_by('-rating_avg')[:10])

        # Entegre açık/kapalı ve cinsiyet bilgisi
        # request context ile main_image tam URL döner (ana uygulama görselleri yükleyebilir)
        serializer = BarbershopHomeSerializer(context={"request": request})
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

        # 4. Campaigns - Sadece onaylı, aktif aboneliği olan ve banlı olmayan barbershop'ların kampanyaları (detay 404 önlemi)
        from app.subscriptions.models import Subscription
        active_campaigns = Campaign.objects.filter(
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
            barbershop__subscription__status__in=['trial', 'active', 'lifetime', 'grace_period'],
            barbershop__is_verified=True,
            barbershop__is_approved=True,  # Sadece onaylı kuaförler; aksi halde detay isteği 404 döner
            barbershop__name__isnull=False
        ).exclude(barbershop__name='').select_related('barbershop')
        
        if city:
            active_campaigns = active_campaigns.filter(barbershop__city__icontains=city)

        campaign_data = []
        for c in active_campaigns[:10]:
            img_url = None
            if c.barbershop.main_image:
                raw_url = c.barbershop.main_image.url
                img_url = request.build_absolute_uri(raw_url) if raw_url else None
            campaign_data.append({
                "id": c.id,
                "title": c.name,
                "type": c.type,
                "shop_id": c.barbershop.id,
                "shop_name": c.barbershop.name,
                "city": c.barbershop.city or "",
                "district": c.barbershop.district or "",
                "discount_value": c.discount_value,
                "discount_type": c.discount_type,
                "image": img_url
            })

        # 5. Announcements - Son 30 günün aktif duyuruları; sadece onaylı kuaförler (detay 404 önlemi)
        from .models import SpecialMessage
        thirty_days_ago = timezone.now() - timedelta(days=30)
        announcements_qs = SpecialMessage.objects.filter(
            is_active=True,
            barbershop__subscription__status__in=['trial', 'active', 'lifetime', 'grace_period'],
            barbershop__is_verified=True,
            barbershop__is_approved=True,  # Sadece onaylı kuaförler; aksi halde detay isteği 404 döner
            barbershop__name__isnull=False,
            created_at__gte=thirty_days_ago
        ).exclude(barbershop__name='').select_related('barbershop').order_by('-created_at')
        
        if city:
            announcements_qs = announcements_qs.filter(barbershop__city__icontains=city)
        
        announcements_data = []
        for ann in announcements_qs[:20]:  # Son 20 duyuru
            announcements_data.append({
                "id": ann.id,
                "barbershop_id": ann.barbershop.id,
                "barbershop_name": ann.barbershop.name,
                "title": ann.title,
                "content": ann.content,
                "display_type": ann.display_type,
                "created_at": ann.created_at.isoformat(),
                "start_datetime": ann.start_datetime.isoformat() if ann.start_datetime else None,
                "end_datetime": ann.end_datetime.isoformat() if ann.end_datetime else None,
            })

        response_data = {
            "categories": cat_data,
            "newest_shops": newest_data,
            "top_rated_shops": top_rated_data,
            "campaigns": campaign_data,
            "announcements": announcements_data
        }
        
        # Cache'e kaydet (2 dakika TTL - kategoriler ve kampanyalar sık değişmez)
        cache.set(cache_key, response_data, 120)  # 2 dakika
        
        return Response(response_data)

