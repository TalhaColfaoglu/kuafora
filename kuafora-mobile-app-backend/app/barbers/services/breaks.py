from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

from django.utils import timezone

from app.barbers.models import (
    Barbershop,
    BreakWindow,
    ShopWorkingHours,
    Staff,
    StaffWorkingHours,
)

WeekdayCode = str
Interval = Tuple[datetime, datetime]


_WEEKDAY_CODES = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}


def weekday_code_for(day: date) -> WeekdayCode:
    return _WEEKDAY_CODES.get(day.weekday(), "MON")


def get_shop_hours(shop: Barbershop, day: date) -> Optional[ShopWorkingHours]:
    code = weekday_code_for(day)
    return ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()


def get_effective_staff_window(staff: Staff, day: date) -> Tuple[Optional[time], Optional[time], bool]:
    """Return (start_time, end_time, inherits_shop)."""
    code = weekday_code_for(day)
    staff_hours = StaffWorkingHours.objects.filter(staff=staff, day_of_week=code).first()
    shop_hours = get_shop_hours(staff.barbershop, day)

    if staff_hours:
        if staff_hours.is_closed:
            return None, None, False
        start = staff_hours.start_time or getattr(shop_hours, "start_time", None)
        end = staff_hours.end_time or getattr(shop_hours, "end_time", None)
        return start, end, False

    if not shop_hours or shop_hours.is_closed:
        return None, None, True
    return shop_hours.start_time, shop_hours.end_time, True


def shop_breaks_for_day(shop: Barbershop, day: date) -> Iterable[BreakWindow]:
    return BreakWindow.objects.filter(
        barbershop=shop,
        scope=BreakWindow.Scope.SHOP,
        date=day,
    ).order_by("start_time")


def staff_breaks_for_day(staff: Staff, day: date) -> Iterable[BreakWindow]:
    return BreakWindow.objects.filter(
        staff=staff,
        scope=BreakWindow.Scope.STAFF,
        date=day,
    ).order_by("start_time")


def collect_break_intervals(shop: Barbershop, staff: Optional[Staff], day: date) -> List[Tuple[datetime, datetime, BreakWindow]]:
    tz = timezone.get_current_timezone()
    intervals: List[Tuple[datetime, datetime, BreakWindow]] = []

    for br in shop_breaks_for_day(shop, day):
        sdt = timezone.make_aware(datetime.combine(day, br.start_time), tz)
        edt = timezone.make_aware(datetime.combine(day, br.end_time), tz)
        intervals.append((sdt, edt, br))

    if staff:
        for br in staff_breaks_for_day(staff, day):
            sdt = timezone.make_aware(datetime.combine(day, br.start_time), tz)
            edt = timezone.make_aware(datetime.combine(day, br.end_time), tz)
            intervals.append((sdt, edt, br))
    return intervals


def current_shop_break(shop: Barbershop, ts: datetime) -> Optional[BreakWindow]:
    day = timezone.localtime(ts).date()
    now_time = timezone.localtime(ts).time()
    return (
        BreakWindow.objects.filter(
            barbershop=shop,
            scope=BreakWindow.Scope.SHOP,
            date=day,
            start_time__lte=now_time,
            end_time__gte=now_time,
        )
        .order_by("start_time")
        .first()
    )


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start


