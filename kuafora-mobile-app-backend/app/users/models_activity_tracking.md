# Kullanıcı Aktivite Tracking Sistemi (Gelecek Özellik)

Bu dosya, gelecekte eklenmesi planlanan kullanıcı aktivite tracking sistemi için bir plan içerir.

## Amaç

Mobil uygulamalarda kullanıcı aktivitelerini detaylı olarak takip etmek için:
- Veri kullanımı (MB/GB)
- Uygulama açılma sayısı (günlük/aylık)
- Session süreleri
- Ekran görüntüleme süreleri

## Önerilen Model Yapısı

```python
class UserActivity(models.Model):
    """Kullanıcı aktivite tracking modeli"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    session_id = models.CharField(max_length=100)  # Her uygulama açılışında unique ID
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    data_used_mb = models.FloatField(default=0.0)  # MB cinsinden veri kullanımı
    screens_viewed = models.JSONField(default=list)  # Görüntülenen ekranlar ve süreleri
    app_version = models.CharField(max_length=20, blank=True)
    device_type = models.CharField(max_length=20, blank=True)  # iOS/Android
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', '-start_time']),
            models.Index(fields=['start_time']),
        ]
```

## API Endpoint Önerisi

```python
# app/users/views.py
class TrackActivityView(generics.CreateAPIView):
    """Kullanıcı aktivitesini kaydet"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserActivitySerializer
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
```

## Dashboard'da Kullanım

Bu model eklendikten sonra dashboard'da şu metrikler gösterilebilir:
- Ortalama günlük uygulama açılma sayısı
- Ortalama veri kullanımı (MB/GB)
- En çok kullanılan ekranlar
- Ortalama session süresi

## Not

Şu an için dashboard `last_login` verisine dayanmaktadır. Bu tracking sistemi eklendikten sonra daha detaylı metrikler gösterilebilir.

