from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from django.core.exceptions import ValidationError
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
    """Dükkan molalarını döndür: önce haftalık periyodik molalar, sonra tarih bazlı özel molalar"""
    code = weekday_code_for(day)
    
    # Haftalık periyodik mola (ShopWorkingHours modelindeki break_start_time/break_end_time)
    shop_hours = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()
    if shop_hours and shop_hours.break_start_time and shop_hours.break_end_time:
        # Haftalık periyodik molayı BreakWindow benzeri bir obje olarak döndür
        # Not: Bu bir gerçek BreakWindow değil, sadece aynı interface'i sağlıyor
        class RecurringBreak:
            def __init__(self, start_time, end_time, shop):
                self.start_time = start_time
                self.end_time = end_time
                self.label = "Mola"
                self.scope = BreakWindow.Scope.SHOP
                self.barbershop = shop
                self.date = day
                self.staff = None
        
        yield RecurringBreak(shop_hours.break_start_time, shop_hours.break_end_time, shop)
    
    # Tarih bazlı özel molalar (BreakWindow - belirli bir tarihe atanmış)
    for br in BreakWindow.objects.filter(barbershop=shop, scope=BreakWindow.Scope.SHOP, date=day).order_by("start_time"):
        yield br


def staff_breaks_for_day(staff: Staff, day: date) -> Iterable[BreakWindow]:
    """Personel molalarını döndür: önce haftalık periyodik molalar, sonra tarih bazlı özel molalar"""
    from datetime import time as _time
    weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
    code = weekday_code_map.get(day.weekday())
    
    # Haftalık periyodik mola (StaffWorkingHours modelindeki break_start_time/break_end_time)
    staff_hours = StaffWorkingHours.objects.filter(staff=staff, day_of_week=code).first()
    if staff_hours and staff_hours.break_start_time and staff_hours.break_end_time:
        # Haftalık periyodik molayı BreakWindow benzeri bir obje olarak döndür
        # Not: Bu bir gerçek BreakWindow değil, sadece aynı interface'i sağlıyor
        class RecurringBreak:
            def __init__(self, start_time, end_time, staff):
                self.start_time = start_time
                self.end_time = end_time
                self.label = "Mola"
                self.scope = BreakWindow.Scope.STAFF
                self.staff = staff
                self.date = day
        
        yield RecurringBreak(staff_hours.break_start_time, staff_hours.break_end_time, staff)
    
    # Tarih bazlı özel molalar (BreakWindow - belirli bir tarihe atanmış)
    for br in BreakWindow.objects.filter(staff=staff, scope=BreakWindow.Scope.STAFF, date=day).order_by("start_time"):
        yield br


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


def validate_break_window_constraints(
    *,
    barbershop: Barbershop,
    staff: Optional[Staff],
    scope: str,
    date_value: date,
    start_time: time,
    end_time: time,
    instance: Optional[BreakWindow] = None,
) -> None:
    """
    Shared doğrulama: çalışma saatleri içinde mi, çakışma var mı?
    Model.clean() ve serializer.validate() tarafından çağrılır.
    """
    if start_time >= end_time:
        raise ValidationError({"start_time": "Başlangıç bitişten küçük olmalı"})

    if scope == BreakWindow.Scope.SHOP:
        shop_hours = get_shop_hours(barbershop, date_value)
        if not shop_hours or shop_hours.is_closed:
            raise ValidationError({"date": "Bu gün dükkan kapalı"})
        open_time = shop_hours.start_time
        close_time = shop_hours.end_time
    else:
        if not staff:
            raise ValidationError({"staff": "Personel molası için staff zorunlu"})
        open_time, close_time, _ = get_effective_staff_window(staff, date_value)
        if not open_time or not close_time:
            raise ValidationError({"date": "Personel bu gün çalışmıyor"})

    if open_time and start_time < open_time:
        raise ValidationError({"start_time": "Mola başlangıcı çalışma saatinden önce"})
    if close_time and end_time > close_time:
        raise ValidationError({"end_time": "Mola bitişi çalışma saatinden sonra"})

    qs = BreakWindow.objects.filter(barbershop=barbershop, scope=scope, date=date_value)
    if staff:
        qs = qs.filter(staff=staff)
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    if qs.filter(start_time__lt=end_time, end_time__gt=start_time).exists():
        raise ValidationError({"date": "Bu saat aralığında mola zaten var"})


def break_windows_by_date(
    *,
    barbershop: Barbershop,
    start_date: date,
    end_date: date,
    include_staff: bool = True,
) -> Dict[date, List[BreakWindow]]:
    qs = BreakWindow.objects.filter(
        barbershop=barbershop,
        date__range=(start_date, end_date),
    )
    if not include_staff:
        qs = qs.filter(scope=BreakWindow.Scope.SHOP)
    qs = qs.select_related("staff__user").order_by("date", "start_time")
    bucket: Dict[date, List[BreakWindow]] = defaultdict(list)
    for br in qs:
        bucket[br.date].append(br)
    return bucket


def serialize_break_window(br: BreakWindow) -> dict:
    return {
        "id": br.id,
        "start": br.start_time,
        "end": br.end_time,
        "label": br.label or ("Dükkan Molası" if br.scope == BreakWindow.Scope.SHOP else "Mola"),
        "scope": br.scope,
        "staff_id": br.staff_id,
        "staff_name": (
            getattr(getattr(br.staff, "user", None), "full_name", None)
            or getattr(getattr(br.staff, "user", None), "email", None)
        )
        if br.staff_id
        else None,
    }


