from django.urls import path

from .views import (
    AvailabilityApi,
    HoldCreateApi,
    AppointmentCreateApi,
    PartnerShiftApi,
    PartnerRescheduleApi,
    PartnerAcceptApi,
    PartnerCancelApi,
    PartnerStatusApi,
    SystemSwitchApi,
    PartnerAppointmentsListApi,
    CustomerAppointmentsApi,
    CustomerAppointmentCancelApi,
)


urlpatterns = [
    path("api/appointments/availability", AvailabilityApi.as_view()),
    path("api/appointments/hold", HoldCreateApi.as_view()),
    path("api/appointments", AppointmentCreateApi.as_view()),
    path("api/appointments/my", CustomerAppointmentsApi.as_view()),
    path("api/appointments/<int:appointment_id>/cancel", CustomerAppointmentCancelApi.as_view()),
    path("api/partner/appointments/<int:appointment_id>/shift", PartnerShiftApi.as_view()),
    path("api/partner/appointments/<int:appointment_id>/reschedule", PartnerRescheduleApi.as_view()),
    path("api/partner/appointments/<int:appointment_id>/accept", PartnerAcceptApi.as_view()),
    path("api/partner/appointments/<int:appointment_id>/cancel", PartnerCancelApi.as_view()),
    path("api/partner/appointments/<int:appointment_id>/status", PartnerStatusApi.as_view()),
    path("api/partner/appointments", PartnerAppointmentsListApi.as_view()),
    path("api/partner/shops/<int:shop_id>/system/switch", SystemSwitchApi.as_view()),
]


