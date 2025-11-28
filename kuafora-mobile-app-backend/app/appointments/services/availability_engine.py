from __future__ import annotations

from datetime import datetime, timedelta, time
from typing import List, Tuple

from django.utils import timezone
from django.db import models

from app.barbers.models import (
    Staff,
    StaffWorkingHours,
    ShopWorkingHours,
    Override,
    Barbershop,
    DailyOverride,
    ShopHolidayOverride,
    BreakWindow,
)
from app.barbers.services.breaks import collect_break_intervals
from app.appointments.models import Appointment


Interval = Tuple[datetime, datetime]


def _align_up(dt: datetime, grid_minutes: int) -> datetime:
    minute = (dt.minute + (grid_minutes - dt.minute % grid_minutes) % grid_minutes)
    aligned = dt.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)
    if aligned < dt:
        aligned += timedelta(minutes=grid_minutes)
    return aligned


def _merge(intervals: List[Interval]) -> List[Interval]:
    if not intervals:
        return []
    intervals.sort(key=lambda x: x[0])
    merged: List[Interval] = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _subtract(base: List[Interval], busy: List[Interval]) -> List[Interval]:
    res: List[Interval] = []
    for b_start, b_end in base:
        cur = [(b_start, b_end)]
        for s, e in busy:
            nxt: List[Interval] = []
            for cs, ce in cur:
                if e <= cs or s >= ce:
                    nxt.append((cs, ce))
                else:
                    if cs < s:
                        nxt.append((cs, s))
                    if e < ce:
                        nxt.append((e, ce))
            cur = nxt
        res.extend(cur)
    return res


def compute_staff_day_slots(*, staff: Staff, shop: Barbershop, date: datetime, duration_minutes: int, grid: int | None = None, include_meta: bool = False):
    tz = timezone.get_current_timezone()
    day = date.date()
    grid_minutes = grid or getattr(staff, "appointment_interval", None) or duration_minutes
    if not grid_minutes:
        grid_minutes = duration_minutes
    break_intervals = collect_break_intervals(shop, staff, day)

    def _serialize_break_windows():
        payload = []
        for _start, _end, br in break_intervals:
            payload.append(
                {
                    "start": br.start_time.strftime("%H:%M"),
                    "end": br.end_time.strftime("%H:%M"),
                    "label": br.label or ("Dükkan Molası" if br.scope == BreakWindow.Scope.SHOP else "Mola"),
                    "scope": br.scope,
                    "staff_id": br.staff_id,
                    "staff_name": getattr(getattr(br.staff, "user", None), "full_name", None)
                    or getattr(getattr(br.staff, "user", None), "email", None),
                }
            )
        return payload

    def _return(slots: List[str], slot_items: Optional[List[dict]] = None):
        if include_meta:
            return {
                "slots": slots,
                "slot_items": slot_items or [],
                "break_windows": _serialize_break_windows(),
            }
        return slots

    def _match_break(slot_start: datetime, slot_end: datetime):
        for b_start, b_end, br in break_intervals:
            if slot_start < b_end and slot_end > b_start:
                return br
        return None

    # NEW: OfficialHoliday check (if not overridden by ShopHolidayOverride, assume default policy might be 'closed' or just informative)
    # However, ShopHolidayOverride is usually created by trigger/signal. If not exists, check raw OfficialHoliday?
    # Currently, we rely on ShopHolidayOverride being present for any official holiday logic.
    # If you want STRICT closing on official holidays if no override exists:
    # from barbers.models import OfficialHoliday
    # if OfficialHoliday.objects.filter(date=day).exists() and not ShopHolidayOverride.objects.filter(barbershop=shop, date=day).exists():
    #    return [] 

    # Check DailyOverride first (highest priority - manual daily toggle)
    daily_override = DailyOverride.objects.filter(barbershop=shop, date=day).first()
    if daily_override and daily_override.status == 'closed':
        return _return([])  # Entire day closed by manual toggle

    # ShopHolidayOverride (official/special day decision at shop level)
    # - closed: entire day closed
    # - custom_hours: restrict base intervals to given window
    holiday_decision = ShopHolidayOverride.objects.filter(barbershop=shop, date=day).first()
    holiday_window: Interval | None = None
    if holiday_decision:
        if getattr(holiday_decision, "status", "") == "closed":
            return _return([])
        if getattr(holiday_decision, "status", "") == "custom_hours":
            if holiday_decision.open_time and holiday_decision.close_time and holiday_decision.open_time < holiday_decision.close_time:
                sdt = timezone.make_aware(datetime.combine(day, holiday_decision.open_time), tz)
                edt = timezone.make_aware(datetime.combine(day, holiday_decision.close_time), tz)
                holiday_window = (sdt, edt)

    # Base working windows from StaffWorkingHours on the weekday
    # Our StaffWorkingHours stores codes as MON..SUN, not Mon/Tue...
    weekday = date.strftime("%a").upper()  # MON/TUE/...
    base_intervals: List[Interval] = []
    
    # Collect StaffWorkingHours for the weekday; support multiple intervals (shifts)
    staff_wh_qs = StaffWorkingHours.objects.filter(staff=staff, day_of_week=weekday, is_closed=False)
    
    # Shop WH resolved once for possible inheritance
    shop_wh = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=weekday, is_closed=False).first()
    
    if staff_wh_qs.exists():
        for wh in staff_wh_qs:
            if wh.start_time and wh.end_time:
                sdt = timezone.make_aware(datetime.combine(day, wh.start_time), tz)
                edt = timezone.make_aware(datetime.combine(day, wh.end_time), tz)
                if sdt < edt:
                    base_intervals.append((sdt, edt))
                # Inject recurring break from StaffWorkingHours
                if wh.break_start_time and wh.break_end_time:
                    bs = timezone.make_aware(datetime.combine(day, wh.break_start_time), tz)
                    be = timezone.make_aware(datetime.combine(day, wh.break_end_time), tz)
                    if bs < be:
                         # Add as a "break interval" to be subtracted later
                         break_intervals.append((bs, be, BreakWindow(
                             start_time=wh.break_start_time, 
                             end_time=wh.break_end_time, 
                             label="Mola",
                             scope=BreakWindow.Scope.STAFF,
                             staff=staff
                         )))
            else:
                # Inherit from shop hours if personel saatleri boş bırakılmışsa
                if shop_wh and shop_wh.start_time and shop_wh.end_time:
                    sdt = timezone.make_aware(datetime.combine(day, shop_wh.start_time), tz)
                    edt = timezone.make_aware(datetime.combine(day, shop_wh.end_time), tz)
                    if sdt < edt:
                        base_intervals.append((sdt, edt))
                    # Inherit shop recurring break? Usually staff override defines breaks.
                    # If inheriting hours, maybe inherit shop breaks too?
                    # Let's support it for consistency.
                    if shop_wh.break_start_time and shop_wh.break_end_time:
                        bs = timezone.make_aware(datetime.combine(day, shop_wh.break_start_time), tz)
                        be = timezone.make_aware(datetime.combine(day, shop_wh.break_end_time), tz)
                        if bs < be:
                            break_intervals.append((bs, be, BreakWindow(
                                start_time=shop_wh.break_start_time, 
                                end_time=shop_wh.break_end_time, 
                                label="Dükkan Molası",
                                scope=BreakWindow.Scope.SHOP,
                                barbershop=shop
                            )))
    else:
        # StaffWorkingHours kaydı yok, dükkan saatlerini kullan
        if shop_wh and shop_wh.start_time and shop_wh.end_time:
            start_dt = timezone.make_aware(datetime.combine(day, shop_wh.start_time), tz)
            end_dt = timezone.make_aware(datetime.combine(day, shop_wh.end_time), tz)
            if start_dt < end_dt:
                base_intervals.append((start_dt, end_dt))
            
            # Shop level recurring break
            if shop_wh.break_start_time and shop_wh.break_end_time:
                bs = timezone.make_aware(datetime.combine(day, shop_wh.break_start_time), tz)
                be = timezone.make_aware(datetime.combine(day, shop_wh.break_end_time), tz)
                if bs < be:
                    break_intervals.append((bs, be, BreakWindow(
                        start_time=shop_wh.break_start_time, 
                        end_time=shop_wh.break_end_time, 
                        label="Dükkan Molası",
                        scope=BreakWindow.Scope.SHOP,
                        barbershop=shop
                    )))

    
    base_intervals = _merge(base_intervals)
    if not base_intervals:
        return _return([])

    # If a shop-level custom-hours holiday window exists, intersect base intervals with it
    if holiday_window:
        restricted: List[Interval] = []
        hw_start, hw_end = holiday_window
        for bs, be in base_intervals:
            s = max(bs, hw_start)
            e = min(be, hw_end)
            if s < e:
                restricted.append((s, e))
        base_intervals = _merge(restricted)
        if not base_intervals:
            return _return([])

    # Apply overrides (only active and matching date)
    # Check both shop global and staff individual overrides
    override_blocks: List[Interval] = []
    
    # Shop global overrides
    for ov in Override.objects.filter(
        barbershop=shop,
        override_type='shop_global',
        is_active=True,
        start_date__lte=day
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=day)
    ):
        if ov.override_scope == "full_day_closed":
            # entire day closed
            return _return([])
        if ov.start_time and ov.end_time:
            sdt = timezone.make_aware(datetime.combine(day, ov.start_time), tz)
            edt = timezone.make_aware(datetime.combine(day, ov.end_time), tz)
            if sdt < edt:
                override_blocks.append((sdt, edt))
    
    # Staff individual overrides
    for ov in Override.objects.filter(
        barbershop=shop,
        staff=staff,
        override_type='staff_individual',
        is_active=True,
        start_date__lte=day
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=day)
    ):
        if ov.override_scope == "full_day_closed":
            # entire day closed for this staff
            return _return([])
        if ov.start_time and ov.end_time:
            sdt = timezone.make_aware(datetime.combine(day, ov.start_time), tz)
            edt = timezone.make_aware(datetime.combine(day, ov.end_time), tz)
            if sdt < edt:
                override_blocks.append((sdt, edt))
    
    # Capture candidate intervals BEFORE subtracting overrides to show them in meta
    candidate_intervals = list(base_intervals)

    if override_blocks:
        # subtract override blocks from base intervals
        base_intervals = _subtract(base_intervals, _merge(override_blocks))
        if not base_intervals:
            return _return([])

    break_blocks = [(bs, be) for bs, be, _ in break_intervals]
    if break_blocks:
        base_intervals = _subtract(base_intervals, _merge(break_blocks))

    # Busy intervals from existing appointments (active statuses)
    busy: List[Interval] = []
    qs = Appointment.objects.filter(staff=staff, start_datetime__date=day).exclude(status__in=["cancelled", "completed", "no_show"])  # type: ignore[list-item]
    for ap in qs:
        busy.append((ap.start_datetime, ap.end_datetime))
    busy = _merge(busy)

    # Free intervals
    free = _subtract(base_intervals, busy)
    if not free:
        return _return([])

    # Grid-aligned slot emission
    slots: List[str] = []
    for fs, fe in free:
        t = _align_up(fs, grid_minutes)
        while t + timedelta(minutes=duration_minutes) <= fe:
            slots.append(t.strftime("%H:%M"))
            t += timedelta(minutes=grid_minutes)
    if not include_meta:
        return slots

    slot_set = set(slots)
    slot_items: List[dict] = []
    seen: set[str] = set()

    def _is_override(s: datetime, e: datetime) -> bool:
        for os, oe in override_blocks:
             if s < oe and e > os: return True
        return False

    for cs, ce in candidate_intervals:
        t = _align_up(cs, grid_minutes)
        while t + timedelta(minutes=duration_minutes) <= ce:
            label = t.strftime("%H:%M")
            if label in seen:
                t += timedelta(minutes=grid_minutes)
                continue
            slot_end = t + timedelta(minutes=duration_minutes)
            br = _match_break(t, slot_end)
            is_available = label in slot_set
            disabled_reason = None
            if not is_available:
                if _is_override(t, slot_end):
                    disabled_reason = "closed"
                elif br:
                    disabled_reason = "break"
                else:
                    disabled_reason = "busy"
            slot_items.append(
                {
                    "time": label,
                    "is_available": is_available,
                    "is_break": bool(br),
                    "disabled_reason": disabled_reason,
                    "break_label": (br.label or "Mola") if br else None,
                    "break_scope": br.scope if br else None,
                    "staff_break": bool(br and br.scope == BreakWindow.Scope.STAFF),
                }
            )
            seen.add(label)
            t += timedelta(minutes=grid_minutes)
    return {
        "slots": slots,
        "slot_items": slot_items,
        "break_windows": _serialize_break_windows(),
    }


