from __future__ import annotations

from datetime import datetime, timedelta, time
from typing import List, Tuple

from django.utils import timezone
from django.db import models

from app.barbers.models import Staff, StaffWorkingHours, Override, Barbershop
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


def compute_staff_day_slots(*, staff: Staff, shop: Barbershop, date: datetime, duration_minutes: int, grid: int | None = None) -> List[str]:
    tz = timezone.get_current_timezone()
    day = date.date()
    grid_minutes = grid or staff.appointment_interval

    # Base working windows from StaffWorkingHours on the weekday
    weekday = date.strftime("%a")  # Mon/Tue...
    base_intervals: List[Interval] = []
    for wh in StaffWorkingHours.objects.filter(staff=staff, day_of_week=weekday):
        start_dt = tz.localize(datetime.combine(day, wh.start_time))
        end_dt = tz.localize(datetime.combine(day, wh.end_time))
        if start_dt < end_dt:
            base_intervals.append((start_dt, end_dt))
    base_intervals = _merge(base_intervals)
    if not base_intervals:
        return []

    # Apply overrides (only active and matching date)
    # For now, handle time range closures and full day closures
    override_blocks: List[Interval] = []
    for ov in Override.objects.filter(barbershop=shop, is_active=True).filter(
        start_date__lte=day
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=day)
    ):
        if ov.override_scope == "full_day_closed":
            # entire day closed
            return []
        if ov.start_time and ov.end_time:
            sdt = tz.localize(datetime.combine(day, ov.start_time))
            edt = tz.localize(datetime.combine(day, ov.end_time))
            if sdt < edt:
                override_blocks.append((sdt, edt))
    if override_blocks:
        # subtract override blocks from base intervals
        base_intervals = _subtract(base_intervals, _merge(override_blocks))
        if not base_intervals:
            return []

    # Busy intervals from existing appointments (active statuses)
    busy: List[Interval] = []
    qs = Appointment.objects.filter(staff=staff, start_datetime__date=day).exclude(status__in=["cancelled", "completed", "no_show"])  # type: ignore[list-item]
    for ap in qs:
        busy.append((ap.start_datetime, ap.end_datetime))
    busy = _merge(busy)

    # Free intervals
    free = _subtract(base_intervals, busy)
    if not free:
        return []

    # Grid-aligned slot emission
    slots: List[str] = []
    for fs, fe in free:
        t = _align_up(fs, grid_minutes)
        while t + timedelta(minutes=duration_minutes) <= fe:
            slots.append(t.strftime("%H:%M"))
            t += timedelta(minutes=grid_minutes)
    return slots


