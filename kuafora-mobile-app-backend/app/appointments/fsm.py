from .models import AppointmentStatus


TRANSITIONS = {
    AppointmentStatus.PENDING: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED, AppointmentStatus.SUGGESTED},
    AppointmentStatus.CONFIRMED: {AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW, AppointmentStatus.CANCELLED},
    AppointmentStatus.SUGGESTED: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED},
}


def can_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    allowed = TRANSITIONS.get(current, set())
    return target in allowed


