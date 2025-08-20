from __future__ import annotations

from django.db.models import Prefetch, Q
from rest_framework import viewsets, mixins, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Barbershop,
    Staff,
    WorkSchedule,
    Review,
    Service,
    Favorite,
)
from .serializers import (
    BarbershopSerializer,
    StaffSerializer,
    WorkScheduleSerializer,
    ReviewSerializer,
    ServiceSerializer,
    FavoriteSerializer,
)
from .filters import BarbershopFilter
from .permissions import IsShopAdmin


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


class FavoriteViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related("barbershop")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PartnerBarbershopViewSet(viewsets.ModelViewSet):
    serializer_class = BarbershopSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        # Partner can manage barbershops where they have admin staff
        user = self.request.user
        return Barbershop.objects.filter(staff__user=user, staff__is_admin=True).distinct()

    @action(detail=True, methods=["patch"], url_path="status")
    def status(self, request, pk=None):
        instance = self.get_object()
        is_verified = request.data.get("is_verified")
        if is_verified is not None:
            instance.is_verified = bool(is_verified)
            instance.save(update_fields=["is_verified"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


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


class PartnerWorkScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = WorkScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return WorkSchedule.objects.filter(staff__barbershop__staff__user=user, staff__barbershop__staff__is_admin=True).select_related("staff")


