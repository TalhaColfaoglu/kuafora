from rest_framework import generics, permissions
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Count, F
from django.shortcuts import get_object_or_404
from datetime import timedelta

from app.barbers.models import Barbershop, Staff
from app.appointments.models import Appointment, AppointmentStatus

class BarbershopAdvancedStatsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Resolve staff/shop
        admin_staff = Staff.objects.filter(user=request.user, is_admin=True).first()
        if not admin_staff:
            # Fallback: check if user is just staff
            admin_staff = Staff.objects.filter(user=request.user).first()
            if not admin_staff:
                return Response({"detail": "Not authorized"}, status=403)
        
        shop = admin_staff.barbershop
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())
        
        # 1. General Overview
        today_qs = Appointment.objects.filter(
            shop=shop, 
            start_datetime__gte=today_start, 
            start_datetime__lt=today_end
        ).exclude(status=AppointmentStatus.CANCELLED)
        
        today_count = today_qs.count()
        
        week_qs = Appointment.objects.filter(
            shop=shop,
            start_datetime__gte=week_start,
            status=AppointmentStatus.COMPLETED
        )
        week_revenue = week_qs.aggregate(total=Sum('price_total'))['total'] or 0
        
        # Occupancy (Simplified: total duration / (staff_count * 9h))
        total_duration = today_qs.aggregate(total=Sum('duration_minutes'))['total'] or 0
        staff_count = Staff.objects.filter(barbershop=shop).count()
        capacity = staff_count * 9 * 60 # 9 hours per staff
        occupancy = (total_duration / capacity * 100) if capacity > 0 else 0
        
        # Top Services (Naive count from service_items JSON)
        # This is heavy on DB if large, but acceptable for now.
        # Better approach: Normalize service items into a separate table.
        service_counts = {}
        for ap in Appointment.objects.filter(shop=shop, created_at__gte=week_start).exclude(status=AppointmentStatus.CANCELLED):
            for item in ap.service_items:
                name = item.get('name', 'Unknown')
                service_counts[name] = service_counts.get(name, 0) + 1
        
        top_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        top_services_list = [{"name": k, "count": v} for k, v in top_services]

        # 2. Staff Analysis
        staff_stats = []
        for s in Staff.objects.filter(barbershop=shop):
            s_qs = Appointment.objects.filter(staff=s, start_datetime__gte=week_start).exclude(status=AppointmentStatus.CANCELLED)
            count = s_qs.count()
            revenue = s_qs.filter(status=AppointmentStatus.COMPLETED).aggregate(t=Sum('price_total'))['t'] or 0
            staff_stats.append({
                "id": s.id,
                "name": s.user.full_name if s.user else "Staff",
                "count": count,
                "revenue": revenue
            })
        
        # 3. Service Revenue Analysis
        # Re-iterate for revenue breakdown
        service_revenue = {}
        for ap in Appointment.objects.filter(shop=shop, start_datetime__gte=week_start, status=AppointmentStatus.COMPLETED):
            for item in ap.service_items:
                name = item.get('name', 'Unknown')
                price = float(item.get('price', 0))
                service_revenue[name] = service_revenue.get(name, 0) + price
        
        revenue_pie = [{"name": k, "value": v} for k, v in service_revenue.items()]
        
        # 4. No-Show Analysis
        no_show_count = Appointment.objects.filter(shop=shop, start_datetime__gte=week_start, status=AppointmentStatus.NO_SHOW).count()
        total_finished = Appointment.objects.filter(shop=shop, start_datetime__gte=week_start, status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW]).count()
        no_show_rate = (no_show_count / total_finished * 100) if total_finished > 0 else 0

        return Response({
            "general": {
                "today_count": today_count,
                "week_revenue": week_revenue,
                "occupancy": round(occupancy, 1),
                "top_services": top_services_list
            },
            "staff": staff_stats,
            "services": {
                "revenue_pie": revenue_pie,
                "no_show_rate": round(no_show_rate, 1)
            }
        })

