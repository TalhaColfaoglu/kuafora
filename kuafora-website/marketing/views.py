from django.shortcuts import render

# Create your views here.


def home(request):
    return render(request, 'marketing/home.html')


def test_buttons(request):
    return render(request, 'test_buttons.html')
