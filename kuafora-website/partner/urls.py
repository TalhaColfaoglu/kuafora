from django.urls import path
from . import views

urlpatterns = [
    path('kuafora-partner/', views.partner_landing, name='partner_landing'),
    path('kuafora-partner/ozellikler/', views.partner_features, name='partner_features'),
    path('kuafora-partner/ekranlar/', views.partner_screens, name='partner_screens'),
    path('kuafora-partner/sss/', views.partner_faq, name='partner_faq'),
]