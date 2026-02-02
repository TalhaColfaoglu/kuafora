from django.shortcuts import render

try:
    from django.contrib.staticfiles.finders import find as static_find
except ImportError:
    def static_find(path):
        return None


def partner_landing(request):
    has_partner_home_image = static_find('img/screens/partner-home.png') is not None
    return render(request, 'partner/partner_landing.html', {'has_partner_home_image': has_partner_home_image})


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


# Legal pages for partner app

def partner_legal_terms(request):
    return render(request, 'partner/legal_terms.html')


def partner_legal_kvkk(request):
    return render(request, 'partner/legal_kvkk.html')


def partner_legal_cookies(request):
    return render(request, 'partner/legal_cookies.html')