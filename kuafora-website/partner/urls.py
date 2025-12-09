from django.urls import path
from . import views

urlpatterns = [
    path('kuafora-partner/', views.partner_landing, name='partner_landing'),
    path('kuafora-partner/ozellikler/', views.partner_features, name='partner_features'),
    path('kuafora-partner/ekranlar/', views.partner_screens, name='partner_screens'),
    path('kuafora-partner/sss/', views.partner_faq, name='partner_faq'),
    path('kuafora-partner/yorumlar/', views.reviews_dashboard, name='reviews_dashboard'),
    path('kuafora-partner/randevular/', views.appointments_dashboard, name='appointments_dashboard'),
    path('kuafora-partner/personel/', views.staff_dashboard, name='staff_dashboard'),
    # Legal pages for partner
    path('kuafora-partner/yasal/kullanim-kosullari/', views.partner_legal_terms, name='partner_legal_terms'),
    path('kuafora-partner/yasal/kvkk-aydinlatma-metni/', views.partner_legal_kvkk, name='partner_legal_kvkk'),
    path('kuafora-partner/yasal/cerez-politikasi/', views.partner_legal_cookies, name='partner_legal_cookies'),
]