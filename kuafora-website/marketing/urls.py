from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('test-buttons/', views.test_buttons, name='test_buttons'),
]
