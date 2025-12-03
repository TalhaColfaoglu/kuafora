from django.shortcuts import render

def partner_landing(request):
    return render(request, 'partner/partner_landing.html')

def partner_features(request):
    return render(request, 'partner/partner_features.html')

def partner_screens(request):
    return render(request, 'partner/partner_screens.html')

def partner_faq(request):
    return render(request, 'partner/partner_faq.html')

def reviews_dashboard(request):
    """Yorumlar yönetim ekranı - kuaförler için"""
    return render(request, 'partner/reviews_dashboard.html')

def appointments_dashboard(request):
    """Randevu yönetim ekranı - kuaförler için"""
    return render(request, 'partner/appointments_dashboard.html')

def staff_dashboard(request):
    """Personel yönetim ekranı - kuaförler için"""
    return render(request, 'partner/staff_dashboard.html')