from django.urls import path
from . import views

urlpatterns = [
    path('kuafora-partner/', views.partner_landing, name='partner_landing'),
    path('kuafora-partner/ozellikler/', views.partner_features, name='partner_features'),
    path('kuafora-partner/ekranlar/', views.partner_screens, name='partner_screens'),
    path('kuafora-partner/sss/', views.partner_faq, name='partner_faq'),
    path('kuafora-partner/yorumlar/', views.reviews_dashboard, name='reviews_dashboard'),
    path('kuafora-partner/randevular/', views.appointments_dashboard, name='appointments_dashboard'),
]