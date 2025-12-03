from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('musteri-uygulamasi/', views.customer_app, name='customer_app'),
    path('test-buttons/', views.test_buttons, name='test_buttons'),
]
