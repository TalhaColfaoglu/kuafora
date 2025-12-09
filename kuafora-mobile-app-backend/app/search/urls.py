from django.urls import path

from .views import SearchHistoryListCreateApi, SearchHistoryClearApi

urlpatterns = [
    path("search/history/", SearchHistoryListCreateApi.as_view(), name="search-history"),
    path("search/history/clear/", SearchHistoryClearApi.as_view(), name="search-history-clear"),
]


