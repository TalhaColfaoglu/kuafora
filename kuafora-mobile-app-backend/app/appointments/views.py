from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, serializers

from app.barbers.models import Barbershop, Staff
from app.users.models import CustomerBan
from .models import Appointment, AppointmentStatus, Hold, ShopSystemSwitchHistory, CancelledBy
from drf_spectacular.utils import extend_schema, inline_serializer
from .permissions import IsBookingEnabled
from .serializers import (
    AvailabilityQuerySerializer,
    AvailabilityResponseSerializer,
    HoldCreateSerializer,
    HoldResponseSerializer,
    AppointmentCreateSerializer,
    AppointmentSerializer,
    ShiftSerializer,
    RescheduleSerializer,
    AppointmentListQuerySerializer,
)
from .services.availability_engine import compute_staff_day_slots
from .services.idempotency import ensure_idempotent, store_idempotent_response
from .services import events
from .fsm import can_transition


class AvailabilityApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        q = AvailabilityQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        data = q.validated_data
        shop = get_object_or_404(Barbershop, pk=data["shop_id"])
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)

        date = datetime.combine(data["date"], datetime.min.time())
        staff_id = data.get("staff_id")
        duration = data["duration"]
        grid = data.get("grid")

        # Enforce strict grid: duration must be divisible by effective grid
        if staff_id:
            staff = get_object_or_404(Staff, pk=staff_id, barbershop=shop)
            effective_grid = grid or staff.appointment_interval
            if effective_grid and duration % int(effective_grid) != 0:
                return Response({"detail": "INVALID_DURATION_GRID"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # When no specific staff is selected, validate only if grid is provided
            if grid and duration % int(grid) != 0:
                return Response({"detail": "INVALID_DURATION_GRID"}, status=status.HTTP_400_BAD_REQUEST)

        if staff_id:
            slots = compute_staff_day_slots(staff=staff, shop=shop, date=timezone.make_aware(date), duration_minutes=duration, grid=grid)
        else:
            # Farketmez: tüm personellerden topla (erken slotlar)
            slots = []
            for staff in Staff.objects.filter(barbershop=shop):
                slots.extend(compute_staff_day_slots(staff=staff, shop=shop, date=timezone.make_aware(date), duration_minutes=duration, grid=grid))
            slots = sorted(list(set(slots)))[:10]

        return Response(AvailabilityResponseSerializer({"slots": slots}).data)


def check_customer_ban(user):
    active_ban = CustomerBan.objects.filter(user=user, expires_at__gt=timezone.now()).first()
    if active_ban:
        remaining = active_ban.expires_at - timezone.now()
        days = remaining.days
        return f"Randevu oluşturamazsınız. Ban sürenizin bitmesine {days} gün kaldı."
    return None


class HoldCreateApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        # Ban check
        ban_msg = check_customer_ban(request.user)
        if ban_msg:
            return Response({"detail": ban_msg, "code": "403_USER_BANNED"}, status=status.HTTP_403_FORBIDDEN)

        s = HoldCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        shop = get_object_or_404(Barbershop, pk=data["shop_id"])
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)
        staff = get_object_or_404(Staff, pk=data["staff_id"], barbershop=shop)

        # recompute availability to verify requested start_time
        date = data["date"]
        start_naive = datetime.combine(date, data["start_time"])  # local date
        start = timezone.make_aware(start_naive)
        duration = 0
        for item in data["service_items"]:
            duration += int(item.get("duration", 0))
        grid = staff.appointment_interval

        # Strict grid validation: total duration must be divisible by grid
        if duration <= 0 or duration % int(grid) != 0:
            return Response({"code": "400_INVALID_DURATION_GRID"}, status=status.HTTP_400_BAD_REQUEST)

        service_items_payload = [dict(item) for item in data["service_items"]]
        total_price = Decimal("0")
        for item in service_items_payload:
            price = item.get("price")
            if price is None:
                continue
            try:
                total_price += Decimal(str(price))
            except (ArithmeticError, ValueError):
                continue
        try:
            total_price = total_price.quantize(Decimal("0.01"))
        except Exception:
            total_price = Decimal("0.00")

        # grid validation
        if start.minute % grid != 0:
            return Response({"code": "409_CONFLICT_GRID"}, status=status.HTTP_409_CONFLICT)

        end = start + timedelta(minutes=duration)
        # naive slot check: reuse engine to see if start exists
        slots = compute_staff_day_slots(staff=staff, shop=shop, date=start, duration_minutes=duration, grid=grid)
        if start.strftime("%H:%M") not in slots:
            return Response({"code": "409_CONFLICT_SLOT"}, status=status.HTTP_409_CONFLICT)

        hold = Hold.objects.create(
            shop=shop,
            staff=staff,
            start_datetime=start,
            end_datetime=end,
            expires_at=timezone.now() + timedelta(seconds=60),
            service_items=service_items_payload,
            price_total=total_price,
        )
        resp = HoldResponseSerializer({"hold_id": hold.pk, "expires_in": 60, "price_total": hold.price_total}).data
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp, status=status.HTTP_200_OK)


class AppointmentCreateApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        # Ban check
        ban_msg = check_customer_ban(request.user)
        if ban_msg:
            return Response({"detail": ban_msg, "code": "403_USER_BANNED"}, status=status.HTTP_403_FORBIDDEN)

        s = AppointmentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        hold = get_object_or_404(Hold.objects.select_for_update(), pk=data["hold_id"])  # lock
        if hold.expires_at <= timezone.now():
            return Response({"detail": "HOLD_EXPIRED"}, status=status.HTTP_409_CONFLICT)
        shop = hold.shop
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)

        # Create appointment (unique constraint protects double booking)
        duration = int((hold.end_datetime - hold.start_datetime).total_seconds() // 60)
        ap = Appointment(
            shop=shop,
            staff=hold.staff,
            customer=request.user if request.user.is_authenticated else None,
            status=AppointmentStatus.CONFIRMED if hold.staff.auto_approval else AppointmentStatus.PENDING,
            start_datetime=hold.start_datetime,
            end_datetime=hold.end_datetime,
            duration_minutes=duration,
            service_items=hold.service_items or [],
            price_total=hold.price_total,
            note=data.get("note", ""),
            source=data.get("source") or "mobile_customer",
        )
        ap.save()
        hold.delete()

        # push: new pending/confirmed appointment
        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_created", "status": ap.status, "id": ap.id})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_created", "status": ap.status, "id": ap.id})

        resp = AppointmentSerializer(ap).data
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp, status=status.HTTP_200_OK)


class PartnerShiftApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, appointment_id: int):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        s = ShiftSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        shift = s.validated_data["shift_minutes"]

        ap = get_object_or_404(Appointment.objects.select_for_update(), pk=appointment_id)
        shop = ap.shop
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)

        grid = ap.staff.appointment_interval
        if abs(shift) > 30:
            return Response({"code": "409_CONFLICT_SHIFT_TOO_LARGE"}, status=status.HTTP_409_CONFLICT)
        if shift % grid != 0:
            return Response({"code": "409_CONFLICT_GRID"}, status=status.HTTP_409_CONFLICT)

        new_start = ap.start_datetime + timedelta(minutes=shift)
        # align (redundant because %grid check above ensures alignment relative to existing)
        if new_start.minute % grid != 0:
            return Response({"code": "409_CONFLICT_GRID"}, status=status.HTTP_409_CONFLICT)
        new_end = new_start + (ap.end_datetime - ap.start_datetime)

        # simple overlap check via creating temp appointment instance and relying on unique constraint when saving
        ap.start_datetime = new_start
        ap.end_datetime = new_end
        # direct confirmed policy
        ap.status = AppointmentStatus.CONFIRMED
        try:
            ap.save()
        except Exception:
            return Response({"code": "409_CONFLICT_SLOT"}, status=status.HTTP_409_CONFLICT)

        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_shifted", "id": ap.id, "new_start": new_start.isoformat()})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_shifted", "id": ap.id, "new_start": new_start.isoformat()})
        resp = {"status": ap.status, "new_start": new_start.isoformat()}
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp, status=status.HTTP_200_OK)


class PartnerRescheduleApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, appointment_id: int):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        s = RescheduleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        new_start = s.validated_data["new_start_dt"]

        ap = get_object_or_404(Appointment.objects.select_for_update(), pk=appointment_id)
        shop = ap.shop
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)
        grid = ap.staff.appointment_interval
        if new_start.minute % grid != 0:
            return Response({"code": "409_CONFLICT_GRID"}, status=status.HTTP_409_CONFLICT)

        new_end = new_start + (ap.end_datetime - ap.start_datetime)
        ap.start_datetime = new_start
        ap.end_datetime = new_end
        ap.status = AppointmentStatus.CONFIRMED
        try:
            ap.save()
        except Exception:
            return Response({"code": "409_CONFLICT_SLOT"}, status=status.HTTP_409_CONFLICT)

        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_rescheduled", "id": ap.id, "new_start": new_start.isoformat()})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_rescheduled", "id": ap.id, "new_start": new_start.isoformat()})
        resp = {"status": ap.status, "new_start": new_start.isoformat()}
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp, status=status.HTTP_200_OK)


class PartnerAcceptApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, appointment_id: int):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        ap = get_object_or_404(Appointment.objects.select_for_update(), pk=appointment_id)
        shop = ap.shop
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)
        if not can_transition(ap.status, AppointmentStatus.CONFIRMED):
            return Response({"detail": "INVALID_TRANSITION"}, status=status.HTTP_400_BAD_REQUEST)
        ap.status = AppointmentStatus.CONFIRMED
        ap.save(update_fields=["status"]) 
        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_accepted", "id": ap.id})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_accepted", "id": ap.id})
        resp = {"status": ap.status}
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp)


class PartnerCancelApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, appointment_id: int):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        ap = get_object_or_404(Appointment.objects.select_for_update(), pk=appointment_id)
        shop = ap.shop
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)
        if ap.status in [AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW]:
            return Response({"detail": "INVALID_TRANSITION"}, status=status.HTTP_400_BAD_REQUEST)
        ap.status = AppointmentStatus.CANCELLED
        
        # Check if rejection (staff action) or just cancel
        # If this endpoint is used by staff to "cancel" a customer appointment, it might be rejection.
        # Usually PartnerCancelApi is used by staff.
        # Let's assume if cancelled via PartnerCancelApi, it is a rejection/cancellation by staff.
        # We can allow passing a reason.
        reason = request.data.get('reason', '')
        ap.rejection_reason = reason
        ap.cancelled_by = CancelledBy.STAFF
        
        ap.save(update_fields=["status", "cancelled_by", "rejection_reason"]) 
        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_cancelled", "id": ap.id})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_cancelled", "id": ap.id})
        resp = {"status": ap.status}
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp)


class PartnerStatusApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, appointment_id: int):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        ap = get_object_or_404(Appointment.objects.select_for_update(), pk=appointment_id)
        shop = ap.shop
        if getattr(shop, "system_type", "info") != "booking":
            return Response({"detail": "BOOKING_DISABLED"}, status=status.HTTP_403_FORBIDDEN)

        target = request.data.get("status")
        if target not in [AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW]:
            return Response({"detail": "INVALID_STATUS"}, status=status.HTTP_400_BAD_REQUEST)
        if not can_transition(ap.status, target):
            return Response({"detail": "INVALID_TRANSITION"}, status=status.HTTP_400_BAD_REQUEST)
        ap.status = target
        ap.save(update_fields=["status"]) 
        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_status", "id": ap.id, "status": ap.status})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_status", "id": ap.id, "status": ap.status})
        resp = {"status": ap.status}
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp)


class SystemSwitchApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, shop_id: int):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(key=idem_key, actor=str(request.user.pk), method="POST", path=request.path, body=request.data)
        if existing is not None:
            return Response(existing)

        shop = get_object_or_404(Barbershop.objects.select_for_update(), pk=shop_id)
        target = request.data.get("target")
        reason = request.data.get("reason", "")
        forced = bool(request.data.get("forced", False))
        if target not in ("info", "booking"):
            return Response({"detail": "INVALID_TARGET"}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        if target == "info":
            # enforce <24h rule
            within24 = Appointment.objects.filter(shop=shop, status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.SUGGESTED], start_datetime__lte=now + timezone.timedelta(hours=24))
            if within24.exists() and not forced:
                return Response({"code": "409_SWITCH_WINDOW"}, status=status.HTTP_409_CONFLICT)
            # cancel all future active appointments
            qs = Appointment.objects.select_for_update().filter(shop=shop, status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.SUGGESTED], start_datetime__gte=now)
            for ap in qs:
                ap.status = AppointmentStatus.CANCELLED
                ap.cancelled_by = "system_switch"
                ap.save(update_fields=["status", "cancelled_by"])
            shop.system_type = "info"
            shop.save(update_fields=["system_type"])
        else:
            # booking target: require working hours presence for at least one staff
            has_hours = (
                Staff.objects.filter(barbershop=shop, work_schedules__isnull=False).exists()
                or Staff.objects.filter(barbershop=shop, staff_working_hours__isnull=False).exists()
            )
            if not has_hours:
                return Response({"code": "400_NO_WORKING_HOURS"}, status=status.HTTP_400_BAD_REQUEST)
            shop.system_type = "booking"
            shop.save(update_fields=["system_type"])

        ShopSystemSwitchHistory.objects.create(shop=shop, from_type="booking" if target == "info" else "info", to_type=target, reason=reason, actor=str(request.user.pk), idempotency_key=idem_key)
        resp = {"system_type": shop.system_type}
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp)


class PartnerAppointmentsListApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        q = AppointmentListQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        data = q.validated_data
        qs = Appointment.objects.all().select_related("staff__user", "shop", "customer")
        staff_id = data.get("staff_id")
        shop_id = data.get("shop_id")
        status_f = data.get("status")
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        if shop_id:
            qs = qs.filter(shop_id=shop_id)
        if status_f:
            qs = qs.filter(status=status_f)
        if date_from:
            qs = qs.filter(start_datetime__gte=date_from)
        if date_to:
            qs = qs.filter(start_datetime__lte=date_to)
        qs = qs.order_by("start_datetime")
        return Response({"items": AppointmentSerializer(qs, many=True).data})


class CustomerAppointmentsApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Müşterinin randevularını listele",
        responses={
            200: inline_serializer(
                name="CustomerAppointmentListResponse",
                fields={
                    "items": AppointmentSerializer(many=True),
                },
            ),
        },
    )
    def get(self, request):
        q = AppointmentListQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        data = q.validated_data
        qs = Appointment.objects.filter(customer=request.user).select_related("staff__user", "shop")
        status_f = data.get("status")
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if status_f:
            qs = qs.filter(status=status_f)
        if date_from:
            qs = qs.filter(start_datetime__gte=date_from)
        if date_to:
            qs = qs.filter(start_datetime__lte=date_to)
        qs = qs.order_by("start_datetime")
        return Response({"items": AppointmentSerializer(qs, many=True).data})


class CustomerAppointmentCancelApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    @extend_schema(
        summary="Müşterinin randevuyu iptal etmesi",
        responses={
            200: inline_serializer(
                name="CustomerAppointmentCancelResponse",
                fields={
                    "status": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, appointment_id: int):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response({"detail": "IDEMPOTENCY_KEY_REQUIRED"}, status=status.HTTP_400_BAD_REQUEST)
        existing = ensure_idempotent(
            key=idem_key,
            actor=str(request.user.pk),
            method="POST",
            path=request.path,
            body=request.data,
        )
        if existing is not None:
            return Response(existing)

        ap = get_object_or_404(
            Appointment.objects.select_for_update(),
            pk=appointment_id,
            customer=request.user,
        )
        if ap.status in [AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW]:
            return Response({"detail": "INVALID_TRANSITION"}, status=status.HTTP_400_BAD_REQUEST)
        if ap.status == AppointmentStatus.CANCELLED:
            resp = {"status": ap.status}
            store_idempotent_response(key=idem_key, response_json=resp)
            return Response(resp)
        if ap.start_datetime <= timezone.now():
            return Response({"detail": "PAST_APPOINTMENT"}, status=status.HTTP_400_BAD_REQUEST)

        ap.status = AppointmentStatus.CANCELLED
        ap.cancelled_by = CancelledBy.CUSTOMER
        ap.save(update_fields=["status", "cancelled_by"])
        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_cancelled", "id": ap.id})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_cancelled", "id": ap.id})
        resp = {"status": ap.status}
        store_idempotent_response(key=idem_key, response_json=resp)
        return Response(resp)


class AppointmentAttendanceApi(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, appointment_id: int):
        """
        Mark appointment attendance status.
        Input: {"status": "attended" | "no_show"}
        """
        new_status = request.data.get("status")
        if new_status not in ["attended", "no_show"]:
            return Response({"detail": "Invalid status. Use 'attended' or 'no_show'."}, status=status.HTTP_400_BAD_REQUEST)

        ap = get_object_or_404(Appointment.objects.select_for_update(), pk=appointment_id)
        
        # Ensure user is authorized staff/admin
        # In a real app, check request.user against ap.staff.user or shop admins
        # Assuming permission checks are handled by DRF permission classes or similar in a robust app.
        # For now, we trust authenticated users who can reach this endpoint have access (since URL routing might be protected or we add explicit check)
        # Let's add a basic check:
        if not (request.user.is_staff or request.user.is_superuser or (ap.staff.user == request.user)):
             # Check if shop admin
             is_shop_admin = Staff.objects.filter(user=request.user, barbershop=ap.shop, is_admin=True).exists()
             if not is_shop_admin:
                 return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        if ap.start_datetime > timezone.now():
             return Response({"detail": "Cannot mark attendance for future appointments."}, status=status.HTTP_400_BAD_REQUEST)

        if new_status == "attended":
            ap.is_attended = True
            ap.status = AppointmentStatus.COMPLETED
        else:
            ap.is_attended = False
            ap.status = AppointmentStatus.NO_SHOW
            
            # Ban logic: Ban for 3 months
            if ap.customer:
                ban_expiry = timezone.now() + timedelta(days=90)
                CustomerBan.objects.create(
                    user=ap.customer,
                    reason="No-show for appointment",
                    expires_at=ban_expiry
                )

        ap.attended_at = timezone.now()
        ap.save(update_fields=["is_attended", "status", "attended_at"])
        
        events.emit(events.staff_topic(ap.staff_id), {"type": "appointment_attendance", "id": ap.id, "status": ap.status})
        events.emit(events.shop_topic(ap.shop_id), {"type": "appointment_attendance", "id": ap.id, "status": ap.status})

        return Response({"status": ap.status, "is_attended": ap.is_attended})
