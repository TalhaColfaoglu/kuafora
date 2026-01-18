from django.urls import path

from .views import SupportRequestCreateApi

urlpatterns = [
    path("support/requests/", SupportRequestCreateApi.as_view(), name="support-request-create"),
]


