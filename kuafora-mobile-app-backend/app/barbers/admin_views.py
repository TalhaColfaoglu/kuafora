"""
Admin-only barbershop "detay ekranı" önizlemesi.
Kuaförün uygulamada nasıl görüneceğini (hizmetler, saatler, personel vb.) tek sayfada gösterir.
"""
from django.shortcuts import get_object_or_404, render
from django.http import Http404

from .models import (
    Barbershop,
    Staff,
    Service,
    ServiceCategory,
    StaffService,
    ShopWorkingHours,
    StaffWorkingHours,
    WorkSchedule,
)

# Gün sırası (API ile uyumlu)
WEEKDAY_ORDER = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
WEEKDAY_LABELS = {
    "MON": "Pazartesi",
    "TUE": "Salı",
    "WED": "Çarşamba",
    "THU": "Perşembe",
    "FRI": "Cuma",
    "SAT": "Cumartesi",
    "SUN": "Pazar",
}

# Özellik ID → Türkçe etiket (uygulama ile uyumlu)
FEATURE_LABELS = {
    "verified": "Doğrulanmış İşletme",
    "instant_conf": "Anında Onay",
    "pay_app": "Uygulama ile Ödeme",
    "adults_only": "Sadece Yetişkin",
    "wheelchair": "Tekerlekli Sandalye Uygun",
    "parking": "Otopark Mevcut",
    "transport": "Toplu Taşıma Yakın",
    "wifi": "WiFi",
    "refreshments": "İkramlar",
    "ac": "Klima",
    "child_friendly": "Çocuk Dostu",
    "pet_friendly": "Evcil Hayvan Dostu",
    "prayer_room": "Mescit",
    "credit_card": "Kredi Kartı Geçerli",
    "cash_only": "Sadece Nakit",
    "security_cam": "Güvenlik Kamerası",
    "valet": "Vale Hizmeti",
    "walkins": "Randevusuz Kabul",
    "silent": "Sessiz Ortam",
    "music": "Müzik Yayını",
    "tv": "TV",
}


def barbershop_preview_view(request, pk):
    """Kuaför detay ekranı önizlemesi — sadece staff kullanıcılar."""
    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404()

    shop = get_object_or_404(
        Barbershop.objects.prefetch_related(
            "images",
            "categories",
            "shop_working_hours",
            "service_categories__services",
            "services__category",
            "staff__staff_services__service",
            "staff__staff_working_hours",
            "staff__work_schedules",
        ),
        pk=pk,
    )

    # Dükkan çalışma saatleri (gün sırasına göre)
    shop_hours = {h.day_of_week: h for h in shop.shop_working_hours.all()}
    shop_schedule = []
    for day in WEEKDAY_ORDER:
        h = shop_hours.get(day)
        if h:
            if h.is_closed:
                shop_schedule.append({"day": WEEKDAY_LABELS.get(day, day), "text": "Kapalı", "closed": True})
            else:
                start = h.start_time.strftime("%H:%M") if h.start_time else "—"
                end = h.end_time.strftime("%H:%M") if h.end_time else "—"
                shop_schedule.append({"day": WEEKDAY_LABELS.get(day, day), "text": f"{start} – {end}", "closed": False})
        else:
            shop_schedule.append({"day": WEEKDAY_LABELS.get(day, day), "text": "—", "closed": False})

    # Hizmetler (kategoriye göre gruplu)
    categories_with_services = []
    for cat in shop.service_categories.all():
        services = list(cat.services.filter(is_active=True).order_by("name"))
        if services:
            categories_with_services.append({"category": cat.name, "services": services})
    # Kategorisiz hizmetler
    uncategorized = list(shop.services.filter(is_active=True, category__isnull=True).order_by("name"))
    if uncategorized:
        categories_with_services.append({"category": "Diğer", "services": uncategorized})

    # Personel + kendi saatleri ve hizmetleri
    staff_list = []
    for s in shop.staff.all():
        # StaffWorkingHours (yeni model) veya WorkSchedule (eski)
        staff_hours = {}
        for h in s.staff_working_hours.all():
            if h.is_closed:
                staff_hours[h.day_of_week] = "Kapalı"
            elif h.start_time and h.end_time:
                staff_hours[h.day_of_week] = f"{h.start_time.strftime('%H:%M')} – {h.end_time.strftime('%H:%M')}"
        if not staff_hours:
            # WorkSchedule uses "Mon", "Tue" etc.
            _day_map = {"Mon": "MON", "Tue": "TUE", "Wed": "WED", "Thu": "THU", "Fri": "FRI", "Sat": "SAT", "Sun": "SUN"}
            for w in s.work_schedules.all():
                day_key = _day_map.get((w.day_of_week or ""), (w.day_of_week or "").upper())
                staff_hours[day_key] = f"{w.start_time.strftime('%H:%M')} – {w.end_time.strftime('%H:%M')}"
        staff_schedule = [{"day": WEEKDAY_LABELS.get(d, d), "text": staff_hours.get(d, "—")} for d in WEEKDAY_ORDER]
        staff_services = list(s.staff_services.filter(is_active=True).select_related("service").order_by("service__name"))
        staff_list.append({
            "staff": s,
            "schedule": staff_schedule,
            "services": staff_services,
        })

    # Özellik etiketleri (features listesi ID, template'te FEATURE_LABELS ile eşleştirilir)
    features_list = getattr(shop, "features", None) or []
    feature_labels_list = [
        {"id": fid, "label": FEATURE_LABELS.get(str(fid), str(fid))}
        for fid in (features_list if isinstance(features_list, list) else [])
    ]

    # Harici randevu (external_booking) – uygulama detay ekranındaki gibi
    external_booking = getattr(shop, "external_booking", None) or {}
    if not isinstance(external_booking, dict):
        external_booking = {}

    # Sistem tipi ve cinsiyet metin
    system_type = getattr(shop, "system_type", None) or "info"
    system_type_display = {
        "info": "Bilgi Sistemi",
        "booking": "Kuafora Randevu",
        "external": "Harici Randevu",
    }.get(system_type, system_type)
    gender = getattr(shop, "gender", None) or "unisex"
    gender_display = {
        "male": "Erkek",
        "female": "Kadın",
        "unisex": "Herkes",
    }.get(gender, gender)

    context = {
        "shop": shop,
        "shop_schedule": shop_schedule,
        "categories_with_services": categories_with_services,
        "staff_list": staff_list,
        "weekday_order": WEEKDAY_ORDER,
        "feature_labels_list": feature_labels_list,
        "external_booking": external_booking,
        "system_type_display": system_type_display,
        "gender_display": gender_display,
    }
    return render(request, "admin/barbers/barbershop_preview.html", context)
