from django.shortcuts import render

def partner_landing(request):
    return render(request, 'partner/partner_landing.html')

def partner_features(request):
    return render(request, 'partner/partner_features.html')

def partner_screens(request):
    return render(request, 'partner/partner_screens.html')

def partner_faq(request):
    return render(request, 'partner/partner_faq.html')