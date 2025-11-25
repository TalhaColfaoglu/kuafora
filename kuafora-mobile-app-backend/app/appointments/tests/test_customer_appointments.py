from datetime import timedelta, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from app.appointments.models import (
    Appointment,
    AppointmentStatus,
    CancelledBy,
    Hold,
    NotificationEvent,
)
from app.barbers.models import Barbershop, Staff, ShopWorkingHours, StaffWorkingHours, BreakWindow


class CustomerAppointmentsAPITest(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(email="customer@example.com", password="pass1234")
        self.other_customer = User.objects.create_user(email="other@example.com", password="pass1234")
        self.staff_user = User.objects.create_user(email="staff@example.com", password="pass1234")
        self.shop = Barbershop.objects.create(
            name="Test Shop",
            gender="unisex",
            address="Test Address",
            city="Istanbul",
            district="Kadikoy",
            phone_number="+900000000000",
            system_type="booking",
        )
        self.staff = Staff.objects.create(
            barbershop=self.shop,
            user=self.staff_user,
            email="staff@example.com",
            auto_approval=True,
        )
        self.staff.appointment_interval = 30
        self.staff.save(update_fields=["appointment_interval"])

    @patch("app.appointments.views.compute_staff_day_slots", return_value=["09:00"])
    def test_hold_and_confirm_persist_service_items(self, _mock_slots):
        self.client.force_authenticate(self.customer)
        target_date = (timezone.now() + timedelta(days=1)).date()
        service_items = [
            {"service": 1, "duration": 20, "price": "100.50"},
            {"service": 2, "duration": 10, "price": "50.25"},
        ]
        hold_resp = self.client.post(
            "/api/appointments/hold",
            {
                "shop_id": self.shop.id,
                "staff_id": self.staff.id,
                "date": target_date.isoformat(),
                "start_time": "09:00",
                "service_items": service_items,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="test-hold-1",
        )
        self.assertEqual(hold_resp.status_code, 200)
        hold_id = hold_resp.data["hold_id"]
        hold = Hold.objects.get(pk=hold_id)
        self.assertEqual(len(hold.service_items), 2)
        self.assertIn({"service": 1, "duration": 20, "price": "100.50"}, hold.service_items)
        self.assertEqual(str(hold.price_total), "150.75")

        confirm_resp = self.client.post(
            "/api/appointments",
            {"hold_id": str(hold_id)},
            format="json",
            HTTP_IDEMPOTENCY_KEY="test-confirm-1",
        )
        self.assertEqual(confirm_resp.status_code, 200)
        appointment = Appointment.objects.get(pk=confirm_resp.data["id"])
        self.assertEqual(appointment.customer, self.customer)
        self.assertEqual(appointment.service_items, hold.service_items)
        self.assertEqual(str(appointment.price_total), "150.75")
        self.assertFalse(Hold.objects.filter(pk=hold_id).exists())

    def test_customer_my_appointments_lists_only_current_user(self):
        future_start = timezone.now() + timedelta(days=2)
        Appointment.objects.create(
            shop=self.shop,
            staff=self.staff,
            customer=self.customer,
            status=AppointmentStatus.CONFIRMED,
            start_datetime=future_start,
            end_datetime=future_start + timedelta(minutes=30),
            duration_minutes=30,
            service_items=[{"service": 1}],
        )
        Appointment.objects.create(
            shop=self.shop,
            staff=self.staff,
            customer=self.other_customer,
            status=AppointmentStatus.CONFIRMED,
            start_datetime=future_start + timedelta(hours=1),
            end_datetime=future_start + timedelta(hours=1, minutes=30),
            duration_minutes=30,
            service_items=[{"service": 2}],
        )

        self.client.force_authenticate(self.customer)
        resp = self.client.get("/api/appointments/my")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["items"]), 1)
        self.assertEqual(resp.data["items"][0]["customer"], self.customer.id)

    def test_customer_cancel_updates_status(self):
        future_start = timezone.now() + timedelta(days=1)
        ap = Appointment.objects.create(
            shop=self.shop,
            staff=self.staff,
            customer=self.customer,
            status=AppointmentStatus.PENDING,
            start_datetime=future_start,
            end_datetime=future_start + timedelta(minutes=30),
            duration_minutes=30,
            service_items=[{"service": 3}],
        )

        self.client.force_authenticate(self.customer)
        resp = self.client.post(
            f"/api/appointments/{ap.id}/cancel",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="cancel-1",
        )
        self.assertEqual(resp.status_code, 200)
        ap.refresh_from_db()
        self.assertEqual(ap.status, AppointmentStatus.CANCELLED)
        self.assertEqual(ap.cancelled_by, CancelledBy.CUSTOMER)
        self.assertGreaterEqual(NotificationEvent.objects.filter(topic__in=[f"staff_{self.staff.id}", f"shop_{self.shop.id}"]).count(), 2)

    def test_availability_returns_break_metadata(self):
        self.client.force_authenticate(self.customer)
        target_date = (timezone.now() + timedelta(days=1)).date()
        weekday_codes = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        code = weekday_codes[target_date.weekday()]
        ShopWorkingHours.objects.create(
            barbershop=self.shop,
            day_of_week=code,
            start_time=time(9, 0),
            end_time=time(18, 0),
            is_closed=False,
        )
        StaffWorkingHours.objects.create(
            staff=self.staff,
            day_of_week=code,
            start_time=time(9, 0),
            end_time=time(18, 0),
            is_closed=False,
        )
        BreakWindow.objects.create(
            barbershop=self.shop,
            scope=BreakWindow.Scope.SHOP,
            date=target_date,
            start_time=time(13, 0),
            end_time=time(13, 30),
            label="Öğle",
            created_by=self.staff_user,
        )

        resp = self.client.get(
            "/api/appointments/availability",
            {
                "shop_id": self.shop.id,
                "staff_id": self.staff.id,
                "date": target_date.isoformat(),
                "duration": 30,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("slots", resp.data)
        self.assertIn("slot_items", resp.data)
        slot_items = resp.data["slot_items"]
        self.assertTrue(any(item.get("is_break") for item in slot_items))
        break_slots = [item for item in slot_items if item.get("is_break")]
        self.assertEqual(break_slots[0].get("disabled_reason"), "break")
        self.assertNotIn("13:00", resp.data["slots"])

