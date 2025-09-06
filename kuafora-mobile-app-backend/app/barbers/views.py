from __future__ import annotations

from django.db.models import Prefetch, Q
from rest_framework import viewsets, mixins, permissions, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from django.utils import timezone

from .models import (
    Favorite,
    
    Barbershop,
    Staff,
    WorkSchedule,
    Review,
    Service,
    LastViewed,
    
)
from .serializers import (
    BarbershopWithFavoriteSerializer,
    
    BarbershopSerializer,
    ReviewSerializer,
    StaffSerializer,
    WorkScheduleSerializer,
    ServiceSerializer,
    LastViewedSerializer,
    InviteStaffSerializer,
    StaffHoursSerializer,
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

    @action(detail=True, methods=["get"], url_path="working-hours")
    def working_hours(self, request, pk=None):
        schedules = WorkSchedule.objects.filter(staff__barbershop_id=pk).select_related("staff")
        serializer = WorkScheduleSerializer(schedules, many=True)
        return Response(serializer.data)

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
        # upsert behavior: update timestamp if exists, trim to last 7
        obj, created = LastViewed.objects.update_or_create(
            user=self.request.user,
            barbershop_id=self.request.data.get('barbershop'),
            defaults={}
        )
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


class PartnerStaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return Staff.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True).select_related("barbershop", "user")

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        data = InviteStaffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"]
        is_admin = data.validated_data.get("is_admin", False)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"detail": "User not found"}, status=404)
        # Attach to first admin barbershop of inviter
        admin_staff = Staff.objects.filter(user=request.user, is_admin=True).select_related("barbershop").first()
        if not admin_staff:
            return Response({"detail": "No admin barbershop"}, status=400)
        Staff.objects.get_or_create(barbershop=admin_staff.barbershop, user=user, defaults={"email": user.email, "is_admin": is_admin})
        return Response({"detail": "Invited/attached"})


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

