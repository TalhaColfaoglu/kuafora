from django.shortcuts import render


def home(request):
    return render(request, 'marketing/home.html')


def customer_app(request):
    return render(request, 'marketing/customer_app.html')

def support(request):
    return render(request, 'marketing/support.html')


def test_buttons(request):
    return render(request, 'test_buttons.html')


# Legal pages for main Kuafora app

def legal_terms(request):
    return render(request, 'marketing/legal_terms.html')


def legal_kvkk(request):
    return render(request, 'marketing/legal_kvkk.html')


def legal_cookies(request):
    return render(request, 'marketing/legal_cookies.html')


def legal_privacy(request):
    return render(request, 'marketing/legal_privacy.html')
