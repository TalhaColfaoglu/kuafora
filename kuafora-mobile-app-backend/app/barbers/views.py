from __future__ import annotations

from django.db.models import Prefetch, Q
from rest_framework import viewsets, mixins, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from .models import (
    Barbershop,
    Staff,
    WorkSchedule,
    Review,
    Service,
    LastViewed,
)
from .serializers import (
    BarbershopSerializer,
    StaffSerializer,
    WorkScheduleSerializer,
    ReviewSerializer,
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

    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request, pk=None):
        reviews = Review.objects.filter(barbershop_id=pk).select_related("user")
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

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
        return LastViewed.objects.filter(user=self.request.user).order_by('-created_at')[:7]

    def perform_create(self, serializer):
        # upsert behavior: update timestamp if exists, trim to last 7
        obj, created = LastViewed.objects.update_or_create(
            user=self.request.user,
            barbershop_id=self.request.data.get('barbershop'),
            defaults={}
        )
        # ensure at most 7 entries
        qs = LastViewed.objects.filter(user=self.request.user).order_by('-created_at')
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


