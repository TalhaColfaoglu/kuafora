from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import ProgrammingError

from .models import SearchHistory
from .serializers import SearchHistorySerializer


class SearchHistoryListCreateApi(generics.ListCreateAPIView):
    """
    Auth'lu kullanıcı için son arama geçmişini döner / yeni kayıt ekler.
    """

    serializer_class = SearchHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or user.is_anonymous:
            return SearchHistory.objects.none()
        # Son 10 kaydı, en yeniler en üstte olacak şekilde döndür.
        #
        # ÖNEMLİ: QuerySet lazy olduğu için (evaluate edilmediği için) ProgrammingError
        # burada değil serializer aşamasında fırlayabiliyor ve 500'e düşebiliyor.
        # Bu yüzden küçük bir "exists()" ile tabloyu erişip hatayı burada yakalıyoruz.
        qs = SearchHistory.objects.filter(user=user).order_by("-created_at")
        try:
            qs.exists()
        except ProgrammingError:
            # Tablo henüz yoksa (migration uygulanmadı) boş dön, 500 atma.
            # Kalıcı çözüm: python manage.py migrate
            return SearchHistory.objects.none()
        return qs[:10]

    def perform_create(self, serializer):
        # Kullanıcının yaptığı her yeni aramayı kaydet
        try:
            serializer.save(user=self.request.user)
        except ProgrammingError:
            # Tablo henüz yoksa (migration uygulanmadı) 500 atma
            # Kalıcı çözüm: migrate
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


