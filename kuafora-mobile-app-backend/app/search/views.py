from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import ProgrammingError

from .models import SearchHistory
from .serializers import SearchHistorySerializer

# En son 7 arama backend'de saklanır; arama ekranında gösterilir
SEARCH_HISTORY_MAX_ITEMS = 7
SEARCH_HISTORY_MAX_AGE_DAYS = 365


class SearchHistoryListCreateApi(generics.ListCreateAPIView):
    """
    Auth'lu kullanıcı için son 7 arama geçmişini döner / yeni kayıt ekler.
    Backend'de saklanır; uygulama açılışında buradan yüklenir.
    """

    serializer_class = SearchHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or user.is_anonymous:
            return SearchHistory.objects.none()
        since = timezone.now() - timedelta(days=SEARCH_HISTORY_MAX_AGE_DAYS)
        qs = SearchHistory.objects.filter(
            user=user,
            created_at__gte=since,
        ).order_by("-created_at")
        try:
            qs.exists()
        except ProgrammingError:
            return SearchHistory.objects.none()
        return qs[:SEARCH_HISTORY_MAX_ITEMS]

    def perform_create(self, serializer):
        # Yeni aramayı kaydet; en son 7 aramayı tut (eskileri sil)
        try:
            serializer.save(user=self.request.user)
            u = self.request.user
            ids_to_keep = list(
                SearchHistory.objects.filter(user=u)
                .order_by("-created_at")[:SEARCH_HISTORY_MAX_ITEMS]
                .values_list("id", flat=True)
            )
            SearchHistory.objects.filter(user=u).exclude(id__in=ids_to_keep).delete()
        except ProgrammingError:
            return


class SearchHistoryClearApi(APIView):
    """
    Kullanıcının tüm arama geçmişini temizler.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            SearchHistory.objects.filter(user=request.user).delete()
            return Response({"detail": "ok"})
        except ProgrammingError:
            # Tablo henüz yoksa (migration uygulanmadı) 500 atma
            # Kalıcı çözüm: migrate
            return Response({"detail": "ok"})


