from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('musteri-uygulamasi/', views.customer_app, name='customer_app'),
    path('destek/', views.support, name='support'),
    path('test-buttons/', views.test_buttons, name='test_buttons'),
    # Legal pages (main app)
    path('yasal/kullanici-sozlesmesi/', views.legal_terms, name='legal_terms'),
    path('yasal/kvkk-aydinlatma-metni/', views.legal_kvkk, name='legal_kvkk'),
    path('yasal/cerez-politikasi/', views.legal_cookies, name='legal_cookies'),
    path('yasal/gizlilik-politikasi/', views.legal_privacy, name='legal_privacy'),
]
