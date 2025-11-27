from datetime import datetime, date, time, timedelta
from typing import List, Dict, Union, Optional
from django.db import transaction
from django.utils import timezone
from app.barbers.models import Barbershop, Staff, Appointment
from app.appointments.models import AppointmentStatus, CancelledBy

def check_and_cancel_conflicts(
    target: Union[Barbershop, Staff],
    new_schedule: List[Dict],
    effective_date: date
):
    """
    Checks active appointments against the new schedule starting from effective_date.
    Cancels appointments that conflict with the new schedule.
    
    new_schedule format: [
        {
            'day_of_week': 'MON',
            'start_time': '09:00', 'end_time': '18:00',
            'break_start_time': '12:00', 'break_end_time': '13:00',
            'is_closed': False
        }, ...
    ]
    """
    # 1. Parse schedule into a lookup dict
    schedule_map = {}
    for item in new_schedule:
        day = item.get('day_of_week')
        if not day:
            continue
        
        # Parse times if strings
        start = item.get('start_time')
        end = item.get('end_time')
        b_start = item.get('break_start_time')
        b_end = item.get('break_end_time')
        
        if isinstance(start, str): start = datetime.strptime(start, '%H:%M:%S' if len(start) > 5 else '%H:%M').time()
        if isinstance(end, str): end = datetime.strptime(end, '%H:%M:%S' if len(end) > 5 else '%H:%M').time()
        if isinstance(b_start, str) and b_start: b_start = datetime.strptime(b_start, '%H:%M:%S' if len(b_start) > 5 else '%H:%M').time()
        if isinstance(b_end, str) and b_end: b_end = datetime.strptime(b_end, '%H:%M:%S' if len(b_end) > 5 else '%H:%M').time()
        
        schedule_map[day] = {
            'start': start,
            'end': end,
            'break_start': b_start,
            'break_end': b_end,
            'is_closed': item.get('is_closed', False)
        }

    # 2. Fetch future appointments
    # Make effective_date aware at start of day
    start_dt = timezone.make_aware(datetime.combine(effective_date, time.min))
    
    active_statuses = [
        AppointmentStatus.PENDING,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.SUGGESTED
    ]
    
    appointments = Appointment.objects.filter(
        status__in=active_statuses,
        start_datetime__gte=start_dt
    )
    
    if isinstance(target, Barbershop):
        appointments = appointments.filter(shop=target)
    else:
        appointments = appointments.filter(staff=target)

    # 3. Check conflicts
    # Weekday mapping: Monday=0 -> 'MON'
    day_codes = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    
    cancelled_count = 0
    
    for appt in appointments:
        # Convert appt times to local time (assuming server timezone matches shop timezone or naive handling)
        # Appointments are stored in UTC usually, but let's rely on timezone.localtime if needed
        # Assuming naive comparison works if everything is normalized, but safer to use local times.
        local_start = timezone.localtime(appt.start_datetime)
        local_end = timezone.localtime(appt.end_datetime)
        
        day_code = day_codes[local_start.weekday()]
        day_config = schedule_map.get(day_code)
        
        if not day_config:
            # No config for this day -> Assume closed or keep existing? 
            # Usually schedule covers all days. If missing, maybe assume closed?
            # Let's skip if missing to be safe, or assume closed.
            # Implementation detail: new_schedule should be complete.
            continue

        conflict_reason = None
        
        if day_config['is_closed']:
            conflict_reason = "Dükkan/Personel bu gün kapalı"
        else:
            # Check working hours bounds
            if day_config['start'] and local_start.time() < day_config['start']:
                conflict_reason = "Randevu mesai başlangıcından önce"
            elif day_config['end'] and local_end.time() > day_config['end']:
                conflict_reason = "Randevu mesai bitişinden sonra"
            
            # Check break overlap
            elif day_config['break_start'] and day_config['break_end']:
                # Overlap logic: (StartA < EndB) and (EndA > StartB)
                # Appt: local_start..local_end
                # Break: break_start..break_end (on the same day)
                
                # Construct break times on the appt date
                appt_date = local_start.date()
                break_start_dt = timezone.make_aware(datetime.combine(appt_date, day_config['break_start']))
                break_end_dt = timezone.make_aware(datetime.combine(appt_date, day_config['break_end']))
                
                if local_start < break_end_dt and local_end > break_start_dt:
                    conflict_reason = "Randevu mola saatine denk geliyor"

        if conflict_reason:
            appt.status = AppointmentStatus.CANCELLED
            appt.cancelled_by = CancelledBy.SYSTEM
            appt.rejection_reason = f"Çalışma saati değişikliği: {conflict_reason}"
            appt.save()
            cancelled_count += 1
            
            # TODO: Send notification (SMS/Push) to customer
            
    return cancelled_count

