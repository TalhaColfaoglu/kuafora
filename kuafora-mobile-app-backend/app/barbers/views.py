from __future__ import annotations

from django.db.models import Prefetch, Q
from rest_framework import viewsets, mixins, permissions, generics, status, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.utils import timezone

from .models import (
    Favorite,
    
    Barbershop,
    Staff,
    WorkSchedule,
    ShopWorkingHours,
    StaffWorkingHours,
    Override,
    SpecialMessage,
    MessageViewLog,
    CalendarAuditLog,
    Review,
    ReviewReply,
    Service,
    ServiceCategory,
    LastViewed,
    ViewEvent,
    
)
from .serializers import (
    BarbershopWithFavoriteSerializer,
    
    BarbershopSerializer,
    ReviewSerializer,
    ReviewReplySerializer,
    StaffSerializer,
    WorkScheduleSerializer,
    ServiceSerializer,
    ServiceCategorySerializer,
    LastViewedSerializer,
    InviteStaffSerializer,
    StaffHoursSerializer,
    ShopWorkingHoursSerializer,
    StaffWorkingHoursSerializer,
    OverrideSerializer,
    SpecialMessageSerializer,
    MessageViewLogSerializer,
    CalendarAuditLogSerializer,
    CalendarStatusSerializer,
    StaffCalendarStatusSerializer,
    WeeklyCalendarSerializer,
)
from .filters import BarbershopFilter
from .permissions import IsShopAdmin
from django.conf import settings


class BarbershopViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Barbershop.objects.all()
        .select_related()
        .prefetch_related("images", "services", "staff")
    )
    serializer_class = BarbershopSerializer
    filterset_class = BarbershopFilter
    search_fields = ("name", "city", "district")

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            if getattr(user, "gender", None) == "male":
                qs = qs.filter(Q(gender="male") | Q(gender="unisex"))
            elif getattr(user, "gender", None) == "female":
                qs = qs.filter(Q(gender="female") | Q(gender="unisex"))
        return qs

    def get_serializer_class(self):
        # Use detail serializer for retrieve to include is_favorited
        if getattr(self, "action", None) == "retrieve":
            from .serializers import BarbershopDetailSerializer
            return BarbershopDetailSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=["get"], url_path="services")
    def services(self, request, pk=None):
        services = Service.objects.filter(barbershop_id=pk, is_active=True)
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="staff")
    def staff(self, request, pk=None):
        staff = Staff.objects.filter(barbershop_id=pk)
        serializer = StaffSerializer(staff, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "put"], url_path="working-hours")
    def working_hours(self, request, pk=None):
        """\
        GET: Haftalık tabloyu (7 gün) MON..SUN kodlarıyla, override'lar uygulanmış şekilde döndür.
             - Öncelik: Global override > Staff override > StaffWorkingHours > ShopWorkingHours
             - Daha kısıtlayıcı olan kazanır.
        PUT: Admin kullanıcı için mağazanın çalışma saatlerini günceller (legacy, korunur).
        """
        if request.method == "GET":
            try:
                shop = Barbershop.objects.get(id=pk)
            except Barbershop.DoesNotExist:
                return Response({"detail": "Barbershop not found"}, status=404)

            code_list = ["MON","TUE","WED","THU","FRI","SAT","SUN"]
            result = []

            for code in code_list:
                # 1) Global override kontrolü
                has_full_closed = Override.objects.filter(
                    barbershop=shop,
                    override_type='shop_global',
                    start_date__lte=timezone.localdate(),  # tarih aralığı bazlı haftalık tablo genel; bugün kapsamlı check yerine record varlığını kontrol ederiz
                    end_date__gte=timezone.localdate(),
                    override_scope='full_day_closed',
                ).exists()

                if has_full_closed:
                    result.append({
                        'day_of_week': code,
                        'start_time': None,
                        'end_time': None,
                        'is_closed': True,
                    })
                    continue

                # 2) StaffWorkingHours (day_code) açık olanlar
                staff_hours = StaffWorkingHours.objects.filter(
                    staff__barbershop=shop,
                    day_of_week=code,
                    is_closed=False,
                )

                # 3) ShopWorkingHours (day_code)
                shop_hours = ShopWorkingHours.objects.filter(
                    barbershop=shop,
                    day_of_week=code,
                ).first()

                if not staff_hours.exists():
                    # Personel varsayılanında çalışan yok; dükkan saatine bak
                    if not shop_hours or shop_hours.is_closed:
                        result.append({
                            'day_of_week': code,
                            'start_time': None,
                            'end_time': None,
                            'is_closed': True,
                        })
                    else:
                        result.append({
                            'day_of_week': code,
                            'start_time': shop_hours.start_time,
                            'end_time': shop_hours.end_time,
                            'is_closed': False,
                        })
                    continue

                # 4) Personel saatlerine göre en erken/birleşik saat aralığı
                candidates_start = []
                candidates_end = []
                for sh in staff_hours:
                    candidates_start.append(sh.start_time or (shop_hours.start_time if shop_hours else None))
                    candidates_end.append(sh.end_time or (shop_hours.end_time if shop_hours else None))
                # None'ları filtrele
                candidates_start = [c for c in candidates_start if c is not None]
                candidates_end = [c for c in candidates_end if c is not None]

                if not candidates_start or not candidates_end:
                    # Bilgi yok; kapalı say
                    result.append({
                        'day_of_week': code,
                        'start_time': None,
                        'end_time': None,
                        'is_closed': True,
                    })
                    continue

                start_time = min(candidates_start)
                end_time = max(candidates_end)

                result.append({
                    'day_of_week': code,
                    'start_time': start_time,
                    'end_time': end_time,
                    'is_closed': False,
                })

            return Response(result)

        # PUT
        if not request.user or not request.user.is_authenticated:
            return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # İsteği yapan kullanıcı bu dükkanda admin mi?
        admin_staff = Staff.objects.filter(barbershop_id=pk, user=request.user, is_admin=True).first()
        if not admin_staff:
            return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        hours = request.data if isinstance(request.data, list) else request.data.get("hours", [])
        if not isinstance(hours, list):
            return Response({"detail": "Invalid payload"}, status=400)

        # Eski saatleri sil, yenilerini ekle
        WorkSchedule.objects.filter(staff=admin_staff).delete()
        serializer = StaffHoursSerializer(data=hours, many=True)
        serializer.is_valid(raise_exception=True)
        for h in serializer.validated_data:
            WorkSchedule.objects.create(staff=admin_staff, **h)
        return Response({"detail": "Updated"})

    @action(detail=True, methods=["get", "post"], url_path="reviews")
    def reviews(self, request, pk=None):
        # POST → upsert
        if request.method == "POST":
            shop = Barbershop.objects.filter(id=pk).first()
            if not shop:
                return Response({"detail": "Barbershop not found"}, status=status.HTTP_404_NOT_FOUND)
            if not request.user or not request.user.is_authenticated:
                return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

            try:
                rating = int(request.data.get("rating"))
            except (TypeError, ValueError):
                rating = None
            if rating is None or rating < 1 or rating > 5:
                return Response({"rating": ["1 ile 5 arasında olmalı."]}, status=400)

            comment = (request.data.get("comment") or "").strip()
            is_anonymous = bool(request.data.get("is_anonymous", False))

            obj, created = Review.objects.update_or_create(
                user=request.user,
                barbershop=shop,
                defaults={"rating": rating, "comment": comment, "is_anonymous": is_anonymous},
            )

            data = ReviewSerializer(obj).data
            shop.refresh_from_db(fields=[
                "rating_avg","total_reviews","star_1_count","star_2_count","star_3_count","star_4_count","star_5_count"
            ])
            meta = {
                "rating_avg": shop.rating_avg,
                "total_reviews": shop.total_reviews,
                "star_counts": {1: shop.star_1_count, 2: shop.star_2_count, 3: shop.star_3_count, 4: shop.star_4_count, 5: shop.star_5_count},
            }
            return Response({"review": data, "meta": meta}, status=201 if created else 200)

        # GET → list with filters/pagination
        qs = Review.objects.filter(barbershop_id=pk).select_related("user")
        stars = request.query_params.get("stars")
        if stars and stars.isdigit():
            qs = qs.filter(rating=int(stars))
        order = request.query_params.get("order", "recent")
        if order == "random":
            qs = qs.order_by("?")
        else:
            qs = qs.order_by("-created_at")

        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10
        start = (page - 1) * page_size
        end = start + page_size
        items = qs[start:end]

        serializer = ReviewSerializer(items, many=True)
        shop = Barbershop.objects.filter(id=pk).first()
        meta = {
            "total": qs.count(),
            "rating_avg": getattr(shop, "rating_avg", 0),
            "total_reviews": getattr(shop, "total_reviews", 0),
            "star_counts": {
                1: getattr(shop, "star_1_count", 0),
                2: getattr(shop, "star_2_count", 0),
                3: getattr(shop, "star_3_count", 0),
                4: getattr(shop, "star_4_count", 0),
                5: getattr(shop, "star_5_count", 0),
            },
        }
        return Response({"items": serializer.data, "meta": meta})
    # reviews action kaldırıldı; public liste ve upsert artık ayrı endpointlerde

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        # Compute open/closed based on today's schedules
        barbershop = Barbershop.objects.filter(pk=pk).first()
        if not barbershop:
            return Response({"detail": "Not found"}, status=404)
        now = timezone.localtime()
        weekday_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        today_code = weekday_map[now.weekday()]
        schedules = (
            WorkSchedule.objects
            .filter(staff__barbershop_id=pk, day_of_week=today_code)
            .values("start_time", "end_time")
        )
        is_open_now = False
        opens_at = None
        closes_at = None
        if schedules:
            for s in schedules:
                start_dt = timezone.make_aware(timezone.datetime.combine(now.date(), s["start_time"]))
                end_dt = timezone.make_aware(timezone.datetime.combine(now.date(), s["end_time"]))
                if start_dt <= now <= end_dt:
                    is_open_now = True
                    opens_at = s["start_time"]
                    closes_at = s["end_time"]
                    break
            if not is_open_now:
                # next opening today
                next_slots = sorted([s for s in schedules if s["start_time"] > now.time()], key=lambda x: x["start_time"])  # type: ignore
                if next_slots:
                    opens_at = next_slots[0]["start_time"]
        return Response({
            "is_open_now": is_open_now,
            "opens_at": opens_at,
            "closes_at": closes_at,
        })


"""Test-only viewset removed"""


class LastViewedViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = LastViewedSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # return last 7 viewed for current user, most recent first
        return LastViewed.objects.filter(user=self.request.user).order_by('-viewed_at')[:7]

    def perform_create(self, serializer):
        # upsert behavior: update-or-create LastViewed and trim to last 7
        obj, created = LastViewed.objects.update_or_create(
            user=self.request.user,
            barbershop_id=self.request.data.get('barbershop'),
            defaults={}
        )
        # Tekrar görüntülemede zaman damgasını güncelle
        if not created:
            try:
                obj.viewed_at = timezone.now()
                obj.save(update_fields=["viewed_at"])
            except Exception:
                pass
        # Her giriş için ViewEvent ekleyerek toplam görüntülenmeyi arttır
        try:
            ViewEvent.objects.create(user=self.request.user, barbershop_id=self.request.data.get('barbershop'))
        except Exception:
            pass
        # ensure at most 7 entries
        qs = LastViewed.objects.filter(user=self.request.user).order_by('-viewed_at')
        ids = list(qs.values_list('id', flat=True))
        if len(ids) > 7:
            LastViewed.objects.filter(id__in=ids[7:]).delete()
        return



class ReviewViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="my")
    def my(self, request):
        """Kullanıcının tüm yorumları (barbershop bilgisiyle)."""
        qs = self.get_queryset().select_related("barbershop")
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PartnerBarbershopViewSet(viewsets.ModelViewSet):
    serializer_class = BarbershopSerializer
    # Allow any authenticated user; queryset restriction + perform_create will enforce admin ownership
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Partner can manage barbershops where they have admin staff
        user = self.request.user
        return Barbershop.objects.filter(staff__user=user, staff__is_admin=True).distinct()

    # No custom permissions; queryset is already restricted to admin-owned shops
    def update(self, request, *args, **kwargs):
        # Admin kuaför ise salon bilgilerini kısmi güncelleyebilir (override)
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        # Sadece belirli alanlar güncellenebilir
        allowed = {"name", "address", "description", "phone", "phone_number", "latitude", "longitude", "city", "district", "gender"}
        data = {k: v for k, v in request.data.items() if k in allowed}
        # phone alias desteği
        if "phone" in data and "phone_number" not in data:
            data["phone_number"] = data.pop("phone")
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="status")
    def status(self, request, pk=None):
        instance = self.get_object()
        is_verified = request.data.get("is_verified")
        if is_verified is not None:
            instance.is_verified = bool(is_verified)
            instance.save(update_fields=["is_verified"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_create(self, serializer):
        barbershop = serializer.save(is_verified=True)
        # Ensure creator is admin staff of this barbershop
        from .models import Staff
        from django.contrib.auth import get_user_model
        user = self.request.user
        Staff.objects.get_or_create(barbershop=barbershop, user=user, defaults={"email": getattr(user, 'email', ''), "is_admin": True})

    @action(detail=False, methods=["get"], url_path="my", permission_classes=[permissions.IsAuthenticated])
    def my_shops(self, request):
        """Kullanıcının personel olduğu (admin veya normal) tüm dükkanlar"""
        qs = Barbershop.objects.filter(staff__user=request.user).distinct()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="images")
    def upload_image(self, request, pk=None):
        from .models import BarbershopImage
        bs = self.get_object()
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'No image'}, status=400)
        BarbershopImage.objects.create(barbershop=bs, image=image)
        return Response({'detail': 'ok'})

    @action(detail=True, methods=["post"], url_path="main-image")
    def set_main_image(self, request, pk=None):
        bs = self.get_object()
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'No image'}, status=400)
        bs.main_image = image
        bs.save(update_fields=["main_image"])
        return Response({'detail': 'ok'})


class PartnerServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return Service.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True).select_related("barbershop")


class ReviewThrottle(UserRateThrottle):
    rate = "10/min"


class ReviewUpsertApi(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ReviewThrottle]

    def post(self, request, barber_id):
        shop = Barbershop.objects.filter(id=barber_id).first()
        if not shop:
            return Response({"detail": "Barbershop not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "rating": request.data.get("rating"),
            "comment": request.data.get("comment", ""),
            "is_anonymous": bool(request.data.get("is_anonymous", False)),
        }
        try:
            rating = int(payload["rating"]) if payload["rating"] is not None else None
        except (TypeError, ValueError):
            rating = None
        if rating is None or rating < 1 or rating > 5:
            return Response({"rating": ["1 ile 5 arasında olmalı."]}, status=400)

        # upsert by (user, barbershop)
        obj, created = Review.objects.update_or_create(
            user=request.user,
            barbershop=shop,
            defaults={
                "rating": rating,
                "comment": payload["comment"],
                "is_anonymous": payload["is_anonymous"],
            },
        )

        data = ReviewSerializer(obj).data
        # snapshot meta
        shop.refresh_from_db(fields=[
            "rating_avg","total_reviews","star_1_count","star_2_count","star_3_count","star_4_count","star_5_count"
        ])
        meta = {
            "rating_avg": shop.rating_avg,
            "total_reviews": shop.total_reviews,
            "star_counts": {
                1: shop.star_1_count, 2: shop.star_2_count, 3: shop.star_3_count, 4: shop.star_4_count, 5: shop.star_5_count
            },
        }
        return Response({"review": data, "meta": meta}, status=201 if created else 200)


class ReviewHighlightsApi(generics.GenericAPIView):
    def get(self, request, barber_id):
        shop = Barbershop.objects.filter(id=barber_id).first()
        if not shop:
            return Response({"detail": "Barbershop not found"}, status=404)
        qs = Review.objects.filter(barbershop=shop).order_by("?")
        # öncelik: yorumlu
        commented = list(qs.exclude(comment="").values_list("id", flat=True)[:50])
        pool = Review.objects.filter(id__in=commented)
        if pool.count() < 3:
            pool = Review.objects.filter(barbershop=shop).order_by("?")
        items = list(pool[:3])
        data = ReviewSerializer(items, many=True).data
        meta = {
            "rating_avg": shop.rating_avg,
            "total_reviews": shop.total_reviews,
            "star_counts": {1: shop.star_1_count, 2: shop.star_2_count, 3: shop.star_3_count, 4: shop.star_4_count, 5: shop.star_5_count},
        }
        return Response({"items": data, "meta": meta})


class BarbershopReviewsListApi(generics.GenericAPIView):
    """Public list endpoint for all reviews of a barbershop with pagination and filters."""
    def get(self, request, barber_id):
        shop = Barbershop.objects.filter(id=barber_id).first()
        if not shop:
            return Response({"detail": "Barbershop not found"}, status=404)

        qs = Review.objects.filter(barbershop=shop).select_related("user")
        stars = request.query_params.get("stars")
        if stars and stars.isdigit():
            qs = qs.filter(rating=int(stars))
        order = request.query_params.get("order", "recent")
        if order == "random":
            qs = qs.order_by("?")
        else:
            qs = qs.order_by("-created_at")

        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10
        start = (page - 1) * page_size
        end = start + page_size
        items = qs[start:end]

        serializer = ReviewSerializer(items, many=True)
        meta = {
            "total": qs.count(),
            "rating_avg": shop.rating_avg,
            "total_reviews": shop.total_reviews,
            "star_counts": {
                1: shop.star_1_count,
                2: shop.star_2_count,
                3: shop.star_3_count,
                4: shop.star_4_count,
                5: shop.star_5_count,
            },
        }
        return Response({"items": serializer.data, "meta": meta})


class PartnerStaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return Staff.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True).select_related("barbershop", "user")

    @action(detail=False, methods=["get"], url_path="my-shops")
    def my_shops(self, request):
        qs = Staff.objects.filter(user=request.user).select_related("barbershop")
        from .serializers import BarbershopSerializer
        shops = [s.barbershop for s in qs if s.barbershop_id]
        data = BarbershopSerializer(shops, many=True).data
        return Response(data)

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        data = InviteStaffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"]
        is_admin = data.validated_data.get("is_admin", False)
        target_barbershop_id = data.validated_data.get("barbershop")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if not user:
            # Kullanıcı yoksa oluştur (parola sıfırlama akışıyla değiştirebilir)
            user = User.objects.create_user(email=email, password=User.objects.make_random_password())
        # Attach to admin's chosen or first barbershop
        admin_staff_qs = Staff.objects.filter(user=request.user, is_admin=True).select_related("barbershop")
        if target_barbershop_id:
            admin_staff = admin_staff_qs.filter(barbershop_id=target_barbershop_id).first()
        else:
            admin_staff = admin_staff_qs.first()
        if not admin_staff:
            return Response({"detail": "No admin barbershop"}, status=400)
        # Aynı kullanıcı birden fazla dükkanda personel olamaz
        exists_any = Staff.objects.filter(user=user).exclude(barbershop=admin_staff.barbershop).exists()
        if exists_any:
            return Response({"detail": "User already attached to another barbershop"}, status=400)
        # Aynı dükkanda zaten varsa tekrarlama
        already = Staff.objects.filter(user=user, barbershop=admin_staff.barbershop).exists()
        if already:
            return Response({"detail": "User already a staff of this barbershop"}, status=409)
        Staff.objects.get_or_create(barbershop=admin_staff.barbershop, user=user, defaults={"email": user.email, "is_admin": is_admin})
        return Response({"detail": "Invited/attached"})

    @action(detail=False, methods=["post"], url_path="attach")
    def attach(self, request):
        data = InviteStaffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"]
        is_admin = data.validated_data.get("is_admin", False)
        target_barbershop_id = data.validated_data.get("barbershop")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"detail": "User not found"}, status=400)
        admin_staff_qs = Staff.objects.filter(user=request.user, is_admin=True).select_related("barbershop")
        if target_barbershop_id:
            admin_staff = admin_staff_qs.filter(barbershop_id=target_barbershop_id).first()
        else:
            admin_staff = admin_staff_qs.first()
        if not admin_staff:
            return Response({"detail": "No admin barbershop"}, status=400)
        exists_any = Staff.objects.filter(user=user).exclude(barbershop=admin_staff.barbershop).exists()
        if exists_any:
            return Response({"detail": "User already attached to another barbershop"}, status=400)
        already = Staff.objects.filter(user=user, barbershop=admin_staff.barbershop).exists()
        if already:
            return Response({"detail": "User already a staff of this barbershop"}, status=409)
        staff = Staff.objects.create(barbershop=admin_staff.barbershop, user=user, email=user.email, is_admin=is_admin)
        return Response(StaffSerializer(staff).data, status=201)


class PartnerWorkScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = WorkScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return WorkSchedule.objects.filter(staff__barbershop__staff__user=user, staff__barbershop__staff__is_admin=True).select_related("staff")

    @action(detail=False, methods=["post"], url_path="set-hours")
    def set_hours(self, request):
        staff_id = request.data.get("staff_id")
        hours = request.data.get("hours", [])
        try:
            staff = Staff.objects.get(id=staff_id, barbershop__staff__user=request.user, barbershop__staff__is_admin=True)
        except Staff.DoesNotExist:
            return Response({"detail": "Staff not found or no permission"}, status=404)
        WorkSchedule.objects.filter(staff=staff).delete()
        serializer = StaffHoursSerializer(data=hours, many=True)
        serializer.is_valid(raise_exception=True)
        for h in serializer.validated_data:
            WorkSchedule.objects.create(staff=staff, **h)
        return Response({"detail": "Updated"})



class FavoriteListView(generics.ListAPIView):
    serializer_class = BarbershopWithFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Barbershop.objects.filter(
            favorited_by__user=self.request.user
        ).order_by("-favorited_by__created_at")


class FavoriteToggleView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, barbershop_id):
        try:
            barbershop = Barbershop.objects.get(id=barbershop_id)
        except Barbershop.DoesNotExist:
            return Response({"error": "Barbershop not found"}, status=404)
        
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            barbershop=barbershop
        )
        
        if not created:
            favorite.delete()
            favorited = False
        else:
            favorited = True
        
        # Update favorites_count
        favorites_count = barbershop.favorited_by.count()
        barbershop.favorites_count = favorites_count
        barbershop.save(update_fields=["favorites_count"])
        
        return Response({"favorited": favorited, "favorites_count": favorites_count})


class PartnerServiceCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return ServiceCategory.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)

    def perform_create(self, serializer):
        # Admin staff'ın barbershop'ını al
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
        serializer.save(barbershop=admin_staff.barbershop)


class PartnerServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return Service.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True).select_related('category')

    def perform_create(self, serializer):
        # Admin staff'ın barbershop'ını al
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
        serializer.save(barbershop=admin_staff.barbershop)

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        """Kategoriler ve altındaki hizmetleri ağaç yapısında döndür"""
        user = request.user
        barbershop_id = request.query_params.get('barbershop')
        
        if not barbershop_id:
            return Response({"detail": "barbershop parameter required"}, status=400)
        
        # Admin staff'ın barbershop'ını kontrol et
        try:
            admin_staff = Staff.objects.get(user=user, is_admin=True, barbershop_id=barbershop_id)
        except Staff.DoesNotExist:
            return Response({"detail": "No permission for this barbershop"}, status=403)
        
        categories = ServiceCategory.objects.filter(barbershop_id=barbershop_id).prefetch_related('services')
        result = []
        
        for category in categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'services': ServiceSerializer(category.services.filter(is_active=True), many=True).data
            }
            result.append(category_data)
        
        return Response(result)


class ReviewReplyViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewReplySerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return ReviewReply.objects.filter(review__barbershop__staff__user=user, review__barbershop__staff__is_admin=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="reply-to-review")
    def reply_to_review(self, request):
        """Bir review'a cevap ver"""
        review_id = request.data.get('review_id')
        text = request.data.get('text')
        
        if not review_id or not text:
            return Response({"detail": "review_id and text required"}, status=400)
        
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return Response({"detail": "Review not found"}, status=404)
        
        # Admin staff'ın bu barbershop'ta yetkisi var mı kontrol et
        try:
            admin_staff = Staff.objects.get(user=request.user, is_admin=True, barbershop=review.barbershop)
        except Staff.DoesNotExist:
            return Response({"detail": "No permission to reply to this review"}, status=403)
        
        # Zaten cevap vermiş mi kontrol et
        if ReviewReply.objects.filter(review=review, user=request.user).exists():
            return Response({"detail": "Already replied to this review"}, status=400)
        
        reply = ReviewReply.objects.create(review=review, user=request.user, text=text)
        return Response(ReviewReplySerializer(reply).data, status=201)


# Takvim ve Mesaj Yönetimi ViewSet'leri
class PartnerShopWorkingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = ShopWorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return ShopWorkingHours.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)

    def perform_create(self, serializer):
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
        serializer.save(barbershop=admin_staff.barbershop)
        self._log_action('create', 'ShopWorkingHours', serializer.instance.id, serializer.validated_data)

    def perform_update(self, serializer):
        old_data = ShopWorkingHoursSerializer(serializer.instance).data
        super().perform_update(serializer)
        self._log_action('update', 'ShopWorkingHours', serializer.instance.id, {
            'old': old_data,
            'new': serializer.validated_data
        })

    def perform_destroy(self, instance):
        old_data = ShopWorkingHoursSerializer(instance).data
        self._log_action('delete', 'ShopWorkingHours', instance.id, old_data)
        super().perform_destroy(instance)

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=changes
            )
        except Staff.DoesNotExist:
            pass


class PartnerStaffWorkingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = StaffWorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return StaffWorkingHours.objects.filter(
            staff__barbershop__staff__user=user, 
            staff__barbershop__staff__is_admin=True
        )

    def perform_create(self, serializer):
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
        # Staff'ın aynı barbershop'ta olduğunu kontrol et
        staff = serializer.validated_data['staff']
        if staff.barbershop != admin_staff.barbershop:
            raise drf_serializers.ValidationError("Bu personel bu barbershop'ta çalışmıyor")
        serializer.save()
        self._log_action('create', 'StaffWorkingHours', serializer.instance.id, serializer.validated_data)

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=changes
            )
        except Staff.DoesNotExist:
            pass


class PartnerOverrideViewSet(viewsets.ModelViewSet):
    serializer_class = OverrideSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return Override.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)

    def perform_create(self, serializer):
        from datetime import datetime, time, timedelta
        from django.utils import timezone as dj_tz
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)

        payload = dict(self.request.data)
        # Yeni API sözleşmesini destekle: scope (shop/staff) + override_type (closed/open/change/break)
        scope_in = (payload.get('scope') or '').lower() if isinstance(payload.get('scope'), str) else ''
        kind_in = (payload.get('override_type') or '').lower() if isinstance(payload.get('override_type'), str) else ''

        mapped_type = None
        mapped_scope = None
        if scope_in in ('shop', 'global'):
            mapped_type = 'shop_global'
        elif scope_in in ('staff', 'personel'):
            mapped_type = 'staff_individual'

        if kind_in in ('closed', 'kapali', 'full_day_closed'):
            mapped_scope = 'full_day_closed'
        elif kind_in in ('break', 'mola', 'time_range_closed'):
            mapped_scope = 'time_range_closed'
        elif kind_in in ('early_closing', 'early'):
            mapped_scope = 'early_closing'
        elif kind_in in ('late_opening', 'late'):
            mapped_scope = 'late_opening'

        # serializer.validated_data içindeki alanları override etmeye çalış
        if mapped_type and 'override_type' in serializer.fields:
            serializer.validated_data['override_type'] = mapped_type
        if mapped_scope and 'override_scope' in serializer.fields:
            serializer.validated_data['override_scope'] = mapped_scope

        # Eğer personel kapsamı seçilmiş ama staff verilmemişse, isteği yapan admin'in staff kaydını ata
        if (serializer.validated_data.get('override_type') or mapped_type) == 'staff_individual' and not serializer.validated_data.get('staff'):
            serializer.validated_data['staff'] = admin_staff

        # Kaydı oluştur
        serializer.save(barbershop=admin_staff.barbershop, created_by=self.request.user)
        self._log_action('create', 'Override', serializer.instance.id, serializer.validated_data)

        # create_message desteği
        create_message_flag = payload.get('create_message')
        try:
            create_message = str(create_message_flag).lower() in ('1', 'true', 'yes')
        except Exception:
            create_message = False

        if create_message:
            # Mesajı otomatik aç
            ov = serializer.instance
            # Başlık ve içerik
            staff_part = f" - {getattr(getattr(ov, 'staff', None), 'user', None) and ov.staff.user.email}" if ov.staff else ''
            title = "Uygun değil" if ov.override_scope == 'full_day_closed' else "Mola / Kısıtlı hizmet"
            title = f"{title}{staff_part}"
            content = ov.reason or ""

            # Zaman aralığı
            start_dt = dj_tz.make_aware(datetime.combine(ov.start_date, ov.start_time or time(0, 0)))
            end_date = ov.end_date or ov.start_date
            # 23:59:59 veya belirtilen end_time
            end_dt = dj_tz.make_aware(datetime.combine(end_date, ov.end_time or time(23, 59)))

            msg = SpecialMessage.objects.create(
                barbershop=admin_staff.barbershop,
                source='automatic',
                display_type=(payload.get('display_type') or 'banner'),
                target_type='all_shop' if not ov.staff else 'specific_staff',
                title=title,
                content=content,
                start_datetime=start_dt,
                end_datetime=end_dt,
                priority=100,
                created_by=self.request.user,
                is_active=True,
            )
            if ov.staff and msg.target_type == 'specific_staff':
                msg.target_staff.add(ov.staff)
            msg.save()

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=changes
            )
        except Staff.DoesNotExist:
            pass

    @action(detail=False, methods=["post"], url_path="quick-override")
    def quick_override(self, request):
        """Hızlı override oluşturma - personel için özel durumlar"""
        staff_id = request.data.get('staff_id')
        override_type = request.data.get('override_type', 'staff_individual')
        scope = request.data.get('scope')
        date = request.data.get('date')
        reason = request.data.get('reason', '')
        
        try:
            admin_staff = Staff.objects.get(user=request.user, is_admin=True)
            staff = Staff.objects.get(id=staff_id, barbershop=admin_staff.barbershop)
            
            override = Override.objects.create(
                barbershop=admin_staff.barbershop,
                staff=staff,
                override_type=override_type,
                override_scope=scope,
                start_date=date,
                reason=reason,
                created_by=request.user
            )
            
            return Response(OverrideSerializer(override).data, status=201)
        except Staff.DoesNotExist:
            return Response({"detail": "Staff not found or no permission"}, status=404)


class PartnerSpecialMessageViewSet(viewsets.ModelViewSet):
    serializer_class = SpecialMessageSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return SpecialMessage.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)

    def perform_create(self, serializer):
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
        serializer.save(barbershop=admin_staff.barbershop, created_by=self.request.user)
        self._log_action('create', 'SpecialMessage', serializer.instance.id, serializer.validated_data)

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=changes
            )
        except Staff.DoesNotExist:
            pass

    @action(detail=False, methods=["get"], url_path="active")
    def active_messages(self, request):
        """Aktif mesajları getir"""
        user = request.user
        try:
            admin_staff = Staff.objects.get(user=user, is_admin=True)
            now = timezone.now()
            
            messages = SpecialMessage.objects.filter(
                barbershop=admin_staff.barbershop,
                is_active=True,
                start_datetime__lte=now,
                end_datetime__gte=now
            ).order_by('-priority', '-created_at')
            
            return Response(SpecialMessageSerializer(messages, many=True).data)
        except Staff.DoesNotExist:
            return Response({"detail": "No permission"}, status=403)


class CalendarStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """Takvim durumu hesaplama ViewSet'i"""
    permission_classes = [permissions.AllowAny]  # Public endpoint
    
    @action(detail=False, methods=["get"], url_path="shop-status")
    def shop_status(self, request):
        """Dükkanın günlük durumunu hesapla"""
        barbershop_id = request.query_params.get('barbershop_id')
        date_str = request.query_params.get('date')
        
        if not barbershop_id or not date_str:
            return Response({"detail": "barbershop_id and date required"}, status=400)
        
        try:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            barbershop = Barbershop.objects.get(id=barbershop_id)
            
            # Takvim hesaplama mantığı burada olacak
            status = self._calculate_shop_status(barbershop, date)
            
            return Response(CalendarStatusSerializer(status).data)
        except (Barbershop.DoesNotExist, ValueError):
            return Response({"detail": "Invalid barbershop or date"}, status=404)

    @action(detail=False, methods=["get"], url_path="staff-status")
    def staff_status(self, request):
        """Personelin günlük durumunu hesapla"""
        staff_id = request.query_params.get('staff_id')
        date_str = request.query_params.get('date')
        
        if not staff_id or not date_str:
            return Response({"detail": "staff_id and date required"}, status=400)
        
        try:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            staff = Staff.objects.get(id=staff_id)
            
            status = self._calculate_staff_status(staff, date)
            
            return Response(StaffCalendarStatusSerializer(status).data)
        except (Staff.DoesNotExist, ValueError):
            return Response({"detail": "Invalid staff or date"}, status=404)

    @action(detail=False, methods=["get"], url_path="weekly")
    def weekly_calendar(self, request):
        """Haftalık takvim görünümü"""
        barbershop_id = request.query_params.get('barbershop_id')
        week_start_str = request.query_params.get('week_start')
        
        if not barbershop_id or not week_start_str:
            return Response({"detail": "barbershop_id and week_start required"}, status=400)
        
        try:
            from datetime import datetime, timedelta
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
            week_end = week_start + timedelta(days=6)
            
            barbershop = Barbershop.objects.get(id=barbershop_id)
            
            # Haftalık verileri topla
            shop_hours = ShopWorkingHours.objects.filter(barbershop=barbershop)
            staff_hours = StaffWorkingHours.objects.filter(staff__barbershop=barbershop)
            overrides = Override.objects.filter(
                barbershop=barbershop,
                start_date__lte=week_end,
                end_date__gte=week_start
            )
            messages = SpecialMessage.objects.filter(
                barbershop=barbershop,
                is_active=True,
                start_datetime__date__lte=week_end,
                end_datetime__date__gte=week_start
            )
            
            weekly_data = {
                'barbershop_id': barbershop.id,
                'week_start': week_start,
                'week_end': week_end,
                'shop_hours': shop_hours,
                'staff_hours': staff_hours,
                'overrides': overrides,
                'messages': messages
            }
            
            return Response(WeeklyCalendarSerializer(weekly_data).data)
        except (Barbershop.DoesNotExist, ValueError):
            return Response({"detail": "Invalid barbershop or date"}, status=404)

    def _calculate_shop_status(self, barbershop, date):
        """Dükkan durumunu hesapla - öncelik sırasına göre"""
        from datetime import datetime, time
        
        # Haftanın günü kodu (MON..SUN)
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(date.weekday())
        
        # 1. Global override kontrolü (en yüksek öncelik)
        global_overrides = Override.objects.filter(
            barbershop=barbershop,
            override_type='shop_global',
            start_date__lte=date,
            end_date__gte=date
        ).order_by('-created_at')
        
        if global_overrides.exists():
            override = global_overrides.first()
            if override.override_scope == 'full_day_closed':
                return {
                    'date': date,
                    'is_open': False,
                    'opening_time': None,
                    'closing_time': None,
                    'status_message': f"Kapalı: {override.reason or 'Özel durum'}",
                    'active_overrides': [override],
                    'active_messages': []
                }
        
        # 2. Personel saatlerini kontrol et
        working_staff = StaffWorkingHours.objects.filter(
            staff__barbershop=barbershop,
            day_of_week=day_code,
            is_closed=False
        )
        
        if not working_staff.exists():
            return {
                'date': date,
                'is_open': False,
                'opening_time': None,
                'closing_time': None,
                'status_message': "Bugün çalışan personel yok",
                'active_overrides': [],
                'active_messages': []
            }
        
        # 3. Dükkan saatlerini al
        shop_hours = ShopWorkingHours.objects.filter(
            barbershop=barbershop,
            day_of_week=day_code
        ).first()
        
        if not shop_hours or shop_hours.is_closed:
            return {
                'date': date,
                'is_open': False,
                'opening_time': None,
                'closing_time': None,
                'status_message': "Dükkan bugün kapalı",
                'active_overrides': [],
                'active_messages': []
            }
        
        # 4. Personel saatlerine göre dükkan saatlerini ayarla
        earliest_start = min([swh.start_time or shop_hours.start_time for swh in working_staff])
        latest_end = max([swh.end_time or shop_hours.end_time for swh in working_staff])
        
        # 5. Aktif mesajları al (ilgili tarih için)
        active_messages = SpecialMessage.objects.filter(
            barbershop=barbershop,
            is_active=True,
            start_datetime__date__lte=date,
            end_datetime__date__gte=date,
            target_type='all_shop'
        ).order_by('-priority')
        
        return {
            'date': date,
            'is_open': True,
            'opening_time': earliest_start,
            'closing_time': latest_end,
            'status_message': None,
            'active_overrides': list(global_overrides),
            'active_messages': list(active_messages)
        }

    def _calculate_staff_status(self, staff, date):
        """Personel durumunu hesapla"""
        # Haftanın günü kodu (MON..SUN)
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(date.weekday())
        # Personel override'larını kontrol et
        staff_overrides = Override.objects.filter(
            staff=staff,
            start_date__lte=date,
            end_date__gte=date
        ).order_by('-created_at')
        
        if staff_overrides.exists():
            override = staff_overrides.first()
            if override.override_scope == 'full_day_closed':
                return {
                    'staff_id': staff.id,
                    'staff_name': staff.user.email,
                    'date': date,
                    'is_working': False,
                    'start_time': None,
                    'end_time': None,
                    'status_message': f"İzinli: {override.reason or 'Özel durum'}",
                    'active_overrides': [override]
                }
        
        # Personel saatlerini al
        staff_hours = StaffWorkingHours.objects.filter(
            staff=staff,
            day_of_week=day_code
        ).first()
        
        if not staff_hours or staff_hours.is_closed:
            return {
                'staff_id': staff.id,
                'staff_name': staff.user.email,
                'date': date,
                'is_working': False,
                'start_time': None,
                'end_time': None,
                'status_message': "Bu gün çalışmıyor",
                'active_overrides': []
            }
        
        # Dükkan saatlerini devral
        shop_hours = ShopWorkingHours.objects.filter(
            barbershop=staff.barbershop,
            day_of_week=day_code
        ).first()
        
        start_time = staff_hours.start_time or (shop_hours.start_time if shop_hours else None)
        end_time = staff_hours.end_time or (shop_hours.end_time if shop_hours else None)
        
        return {
            'staff_id': staff.id,
            'staff_name': staff.user.email,
            'date': date,
            'is_working': True,
            'start_time': start_time,
            'end_time': end_time,
            'status_message': None,
            'active_overrides': list(staff_overrides)
        }

