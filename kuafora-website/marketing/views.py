from django.shortcuts import render

# Create your views here.


def home(request):
    return render(request, 'marketing/home.html')


def customer_app(request):
    return render(request, 'marketing/customer_app.html')


def test_buttons(request):
    return render(request, 'test_buttons.html')
