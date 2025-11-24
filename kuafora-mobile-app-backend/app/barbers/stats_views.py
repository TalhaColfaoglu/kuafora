from rest_framework import generics, permissions
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from datetime import timedelta, datetime
from app.barbers.models import Barbershop, Staff, ViewEvent, Favorite, Review
from app.appointments.models import Appointment, AppointmentStatus

class BarbershopAdvancedStatsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # 1. Identify Staff/Shop
        try:
            # Try to find staff profile for the user
            admin_staff = Staff.objects.filter(user=request.user).first()
            if not admin_staff:
                return Response({"detail": "Yetkili personel profili bulunamadı."}, status=403)
            shop = admin_staff.barbershop
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        # 2. Parse Date Range (defaults to "Today")
        now = timezone.now()
        today = now.date()
        
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        if start_str and end_str:
            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = today
                end_date = today
        else:
            # Default: Today
            start_date = today
            end_date = today

        # Make timezone-aware datetimes for DB queries
        range_start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        range_end = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

        # Calculate Previous Period for Trends
        delta = end_date - start_date
        days_diff = delta.days + 1
        # Prev period ends just before current period starts
        prev_end = range_start - timedelta(microseconds=1)
        prev_start = prev_end - timedelta(days=days_diff) + timedelta(microseconds=1)

        def calc_trend(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)

        # --- A. INTERACTION METRICS (For ALL Shops) ---
        
        # 1. Total Views
        curr_views = ViewEvent.objects.filter(barbershop=shop, viewed_at__range=(range_start, range_end)).count()
        prev_views = ViewEvent.objects.filter(barbershop=shop, viewed_at__range=(prev_start, prev_end)).count()
        
        # 2. Unique Visitors
        curr_unique = ViewEvent.objects.filter(barbershop=shop, viewed_at__range=(range_start, range_end)).values('user').distinct().count()
        prev_unique = ViewEvent.objects.filter(barbershop=shop, viewed_at__range=(prev_start, prev_end)).values('user').distinct().count()

        # 3. Favorites Gained
        curr_favs = Favorite.objects.filter(barbershop=shop, created_at__range=(range_start, range_end)).count()
        prev_favs = Favorite.objects.filter(barbershop=shop, created_at__range=(prev_start, prev_end)).count()

        # 4. Reviews Received
        curr_reviews = Review.objects.filter(barbershop=shop, created_at__range=(range_start, range_end)).count()
        prev_reviews = Review.objects.filter(barbershop=shop, created_at__range=(prev_start, prev_end)).count()

        interactions = {
            "views": {"total": curr_views, "trend": calc_trend(curr_views, prev_views)},
            "unique_visitors": {"total": curr_unique, "trend": calc_trend(curr_unique, prev_unique)},
            "favorites": {"total": curr_favs, "trend": calc_trend(curr_favs, prev_favs)},
            "reviews": {"total": curr_reviews, "trend": calc_trend(curr_reviews, prev_reviews)},
        }

        # --- B. REVIEWS LIST (For ALL Shops) ---
        reviews_qs = Review.objects.filter(
            barbershop=shop, 
            created_at__range=(range_start, range_end)
        ).select_related('user', 'staff').order_by('-created_at')[:20]

        reviews_data = []
        for r in reviews_qs:
            u_name = "Anonim"
            if not r.is_anonymous and r.user:
                u_name = getattr(r.user, 'full_name', r.user.email.split('@')[0])
            
            staff_name = None
            if r.staff and r.staff.user:
                 staff_name = getattr(r.staff.user, 'full_name', None)

            reviews_data.append({
                "id": r.id,
                "user_name": u_name,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at,
                "staff_name": staff_name
            })


        # --- C. BOOKING METRICS (Only if Booking System) ---
        booking_stats = None
        staff_performance = []
        top_services = []
        daily_chart = []
        
        if shop.system_type == 'booking':
            appts = Appointment.objects.filter(shop=shop, start_datetime__range=(range_start, range_end))
            
            # Counts
            total_appts = appts.count()
            confirmed = appts.filter(status=AppointmentStatus.CONFIRMED).count()
            completed = appts.filter(status=AppointmentStatus.COMPLETED).count()
            cancelled = appts.filter(status=AppointmentStatus.CANCELLED).count()
            no_show = appts.filter(status=AppointmentStatus.NO_SHOW).count()
            
            # Revenue
            revenue_agg = appts.filter(status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.CONFIRMED]).aggregate(total=Sum('price_total'))
            total_revenue = revenue_agg['total'] or 0

            # Prev Revenue
            prev_appts = Appointment.objects.filter(shop=shop, start_datetime__range=(prev_start, prev_end))
            prev_rev_agg = prev_appts.filter(status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.CONFIRMED]).aggregate(total=Sum('price_total'))
            prev_revenue = prev_rev_agg['total'] or 0
            revenue_trend = calc_trend(total_revenue, prev_revenue)

            # Occupancy
            total_minutes = appts.filter(status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.CONFIRMED]).aggregate(mins=Sum('duration_minutes'))
            booked_minutes = total_minutes['mins'] or 0
            
            staff_count = shop.staff.count()
            capacity_minutes = staff_count * days_diff * 600 # Approx 10h/day
            occupancy_rate = 0
            if capacity_minutes > 0:
                occupancy_rate = round((booked_minutes / capacity_minutes) * 100, 1)

            # No Show Rate
            finished_count = completed + no_show
            no_show_rate = 0
            if finished_count > 0:
                no_show_rate = round((no_show / finished_count) * 100, 1)

            booking_stats = {
                "revenue": {"total": total_revenue, "trend": revenue_trend},
                "counts": {
                    "total": total_appts,
                    "confirmed": confirmed,
                    "completed": completed,
                    "cancelled": cancelled,
                    "no_show": no_show
                },
                "occupancy_rate": occupancy_rate,
                "no_show_rate": no_show_rate
            }

            # Staff Performance
            # Adjusted query to use 'full_name' instead of 'first_name'/'last_name'
            staff_qs = appts.values('staff__user__full_name').annotate(
                count=Count('id'),
                revenue=Sum('price_total', filter=Q(status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.CONFIRMED]))
            ).order_by('-revenue')
            
            for s in staff_qs:
                name = (s['staff__user__full_name'] or "").strip() or "Personel"
                staff_performance.append({
                    "name": name,
                    "count": s['count'],
                    "revenue": s['revenue'] or 0
                })

            # Top Services
            valid_appts = appts.filter(status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.CONFIRMED])
            service_map = {}
            for ap in valid_appts:
                items = ap.service_items or []
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            s_name = item.get('name', 'Bilinmeyen')
                            s_price = float(item.get('price', 0))
                            if s_name not in service_map:
                                service_map[s_name] = {"count": 0, "revenue": 0}
                            service_map[s_name]["count"] += 1
                            service_map[s_name]["revenue"] += s_price

            top_services = [
                {"name": k, "count": v["count"], "revenue": v["revenue"]}
                for k, v in service_map.items()
            ]
            top_services.sort(key=lambda x: x['revenue'], reverse=True)
            top_services = top_services[:5]
            
            # Daily Chart Data (Simple: Revenue & Count per day)
            # Group by date (trunc)
            # Django TruncDate is useful here
            from django.db.models.functions import TruncDate
            daily_qs = appts.annotate(date=TruncDate('start_datetime')).values('date').annotate(
                count=Count('id'),
                revenue=Sum('price_total', filter=Q(status__in=[AppointmentStatus.COMPLETED, AppointmentStatus.CONFIRMED]))
            ).order_by('date')
            
            for d in daily_qs:
                daily_chart.append({
                    "date": d['date'],
                    "count": d['count'],
                    "revenue": d['revenue'] or 0
                })


        return Response({
            "system_type": shop.system_type,
            "date_range": {
                "start": start_date,
                "end": end_date,
                "days": days_diff
            },
            "interactions": interactions,
            "reviews_list": reviews_data,
            "booking_stats": booking_stats,
            "staff_performance": staff_performance,
            "top_services": top_services,
            "daily_chart": daily_chart
        })
