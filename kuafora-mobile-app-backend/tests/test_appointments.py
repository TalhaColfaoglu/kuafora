import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from datetime import datetime, time, timedelta

from app.barbers.models import Barbershop, Staff, StaffWorkingHours
from app.appointments.models import Appointment, AppointmentStatus, Hold


@pytest.fixture
def api_client(db):
    return APIClient()


@pytest.fixture
def user(db):
    U = get_user_model()
    return U.objects.create_user(email="test@example.com", password="pass1234")


@pytest.fixture
def shop(db):
    return Barbershop.objects.create(name="Test Shop", gender="unisex", address="addr", city="Istanbul", district="Besiktas", phone_number="123", system_type="booking")


@pytest.fixture
def staff(db, user, shop):
    s = Staff.objects.create(barbershop=shop, user=user, email=user.email, appointment_interval=10, auto_approval=True)
    # Monday working hours 09:00-12:00
    StaffWorkingHours.objects.create(staff=s, day_of_week="Mon", start_time=time(9,0), end_time=time(12,0))
    return s


def auth(client: APIClient, user):
    client.force_authenticate(user=user)


def test_availability_duration_fit(db, api_client, user, shop, staff):
    auth(api_client, user)
    # Place an appointment at 09:30-10:00
    tz = timezone.get_current_timezone()
    start = tz.localize(datetime.combine(datetime.today().date(), time(9,30)))
    ap = Appointment.objects.create(shop=shop, staff=staff, customer=user, status=AppointmentStatus.CONFIRMED, start_datetime=start, end_datetime=start+timedelta(minutes=30), duration_minutes=30)

    date = datetime.today().date()
    # duration 45 should not include 09:30
    resp = api_client.get("/api/appointments/availability", {
        "shop_id": shop.id,
        "staff_id": staff.id,
        "date": date.isoformat(),
        "duration": 45,
        "grid": 10,
    })
    assert resp.status_code == 200
    assert "09:30" not in resp.data["slots"]


def test_hold_confirm_race(db, api_client, user, shop, staff):
    auth(api_client, user)
    tz = timezone.get_current_timezone()
    date = datetime.today().date()
    start = time(10, 0)
    headers = {"HTTP_IDEMPOTENCY_KEY": "k1"}
    resp1 = api_client.post("/api/appointments/hold", {
        "shop_id": shop.id,
        "staff_id": staff.id,
        "date": date.isoformat(),
        "start_time": start.isoformat(),
        "service_items": [{"service_id": 1, "duration": 30, "price": 100}],
    }, format='json', **headers)
    assert resp1.status_code == 200
    hold_id = resp1.data["hold_id"]
    # second hold same slot
    headers2 = {"HTTP_IDEMPOTENCY_KEY": "k2"}
    resp2 = api_client.post("/api/appointments/hold", {
        "shop_id": shop.id,
        "staff_id": staff.id,
        "date": date.isoformat(),
        "start_time": start.isoformat(),
        "service_items": [{"service_id": 1, "duration": 30, "price": 100}],
    }, format='json', **headers2)
    assert resp2.status_code == 200

    # confirm first
    c1 = api_client.post("/api/appointments", {"hold_id": hold_id}, format='json', **{"HTTP_IDEMPOTENCY_KEY": "c1"})
    assert c1.status_code == 200
    # confirm second should conflict
    hold2 = resp2.data["hold_id"]
    c2 = api_client.post("/api/appointments", {"hold_id": hold2}, format='json', **{"HTTP_IDEMPOTENCY_KEY": "c2"})
    assert c2.status_code == 409


def test_shift_rules(db, api_client, user, shop, staff):
    auth(api_client, user)
    tz = timezone.get_current_timezone()
    start = tz.localize(datetime.combine(datetime.today().date(), time(11,0)))
    ap = Appointment.objects.create(shop=shop, staff=staff, customer=user, status=AppointmentStatus.CONFIRMED, start_datetime=start, end_datetime=start+timedelta(minutes=30), duration_minutes=30)

    # too large
    r1 = api_client.post(f"/api/partner/appointments/{ap.id}/shift", {"shift_minutes": 40}, format='json', **{"HTTP_IDEMPOTENCY_KEY": "s1"})
    assert r1.status_code == 409
    # not grid aligned
    r2 = api_client.post(f"/api/partner/appointments/{ap.id}/shift", {"shift_minutes": 7}, format='json', **{"HTTP_IDEMPOTENCY_KEY": "s2"})
    assert r2.status_code == 409
    # ok
    r3 = api_client.post(f"/api/partner/appointments/{ap.id}/shift", {"shift_minutes": 20}, format='json', **{"HTTP_IDEMPOTENCY_KEY": "s3"})
    assert r3.status_code == 200


def test_booking_disabled_guard(db, api_client, user):
    auth(api_client, user)
    shop = Barbershop.objects.create(name="Info Shop", gender="unisex", address="a", city="Istanbul", district="Besiktas", phone_number="123", system_type="info")
    # Availability should return 403
    date = datetime.today().date().isoformat()
    resp = api_client.get("/api/appointments/availability", {"shop_id": shop.id, "date": date, "duration": 30})
    assert resp.status_code == 403

