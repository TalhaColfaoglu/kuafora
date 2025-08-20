from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from django.http import JsonResponse
def health(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/auth/", include("app.users.urls")),
    path("api/", include("app.barbers.urls")),
    path("api/", include("app.uploads.urls")),
    path("health/", health),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


