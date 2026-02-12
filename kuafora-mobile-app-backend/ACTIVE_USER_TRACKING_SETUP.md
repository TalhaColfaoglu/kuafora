# Aktif Kullanıcı Tracking Sistemi - Kurulum ve Kullanım

## 🎯 Genel Bakış

Admin dashboard'da aktif kullanıcı metriklerini (DAU, WAU, MAU, YAU) doğru bir şekilde göstermek için yeni bir tracking sistemi eklendi.

### Yapılan Değişiklikler:

1. **Yeni Modeller Eklendi:**
   - `UserActivityLog`: Her gün her cihaz için giriş kaydı tutar
   - `DailyMetrics`: Günlük metrics snapshot'ları saklar (tarihsel veri)

2. **Signals Eklendi:** Otomatik kullanıcı aktivite tracking
3. **Management Command:** Günlük metrics hesaplama
4. **Dashboard Güncellemeleri:** UserActivityLog kullanarak doğru aktif kullanıcı sayımı
5. **Utility Functions:** API endpoint'lerden kolay tracking

---

## 📋 Kurulum Adımları

### 1. Database Migrations

```bash
# SSH ile sunucuya bağlan
ssh -i ~/Downloads/makas-deneme.pem ubuntu@3.122.14.242

# Docker container içinde migrations oluştur
docker exec -it kuafora-backend bash
python manage.py makemigrations analytics
python manage.py migrate analytics

# Container'dan çık
exit
```

### 2. Test Et

```bash
# Yeni modellerin çalıştığını doğrula
docker exec -it kuafora-backend bash
python manage.py shell

# Shell'de:
from app.analytics.models import UserActivityLog, DailyMetrics
print("UserActivityLog model:", UserActivityLog.objects.count())
print("DailyMetrics model:", DailyMetrics.objects.count())
exit()
```

---

## 🔧 API Entegrasyonu

### Mobil App Login/Authentication Endpoint'lerinde Kullanım

Mobil uygulama kullanıcıları her giriş yaptığında tracking yapılmalı.

#### Örnek: Login View'de Tracking

```python
# app/users/views.py veya authentication view'lerinde

from app.analytics.utils import track_login
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    # ... authentication işlemleri ...
    
    # Kullanıcı başarıyla giriş yaptıktan sonra:
    if user.is_authenticated:
        # Tracking ekle
        device_id = request.data.get('device_id')  # Mobil uygulama gönderir
        platform = request.data.get('platform', 'unknown')  # iOS, Android
        app_version = request.data.get('app_version', '')
        os_version = request.data.get('os_version', '')
        
        track_login(
            user=user,
            device_id=device_id,
            app_type='main',  # main: mobil app, partner: partner app
            request=request,
            platform=platform,
            app_version=app_version,
            os_version=os_version
        )
    
    return Response({'token': token, 'user': user_data})
```

#### Örnek: Token Refresh Endpoint'te Lightweight Tracking

```python
from app.analytics.utils import track_activity

@api_view(['POST'])
def token_refresh_view(request):
    # ... token refresh işlemleri ...
    
    # Lightweight tracking (session oluşturmaz, sadece activity log)
    if request.user and request.user.is_authenticated:
        device_id = request.data.get('device_id')
        track_activity(
            user=request.user,
            device_id=device_id,
            app_type='main',
            request=request
        )
    
    return Response({'token': new_token})
```

#### Örnek: ViewSet Mixin ile Otomatik Tracking

```python
from app.analytics.utils import ActivityTrackingMixin
from rest_framework import viewsets

class MyAPIViewSet(ActivityTrackingMixin, viewsets.ModelViewSet):
    # Her API isteğinde otomatik tracking
    
    def list(self, request, *args, **kwargs):
        # Kullanıcı aktivitesini track et
        self.track_user_activity(request, app_type='main')
        
        # Normal işlem
        return super().list(request, *args, **kwargs)
```

---

## ⚙️ Management Commands

### Günlük Metrics Hesaplama

```bash
# Manuel olarak dünün metriklerini hesapla
docker exec -it kuafora-backend python manage.py calculate_daily_metrics

# Belirli bir gün için
docker exec -it kuafora-backend python manage.py calculate_daily_metrics --date 2026-02-11

# Son 30 günü backfill et
docker exec -it kuafora-backend python manage.py calculate_daily_metrics --backfill 30
```

### Cron Job Kurulumu (Günlük Otomatik Çalıştırma)

Sunucuya cron job ekle:

```bash
# Crontab düzenle
crontab -e

# Her gün sabah 01:00'de metrics hesapla
0 1 * * * docker exec kuafora-backend python manage.py calculate_daily_metrics >> /home/ubuntu/logs/daily_metrics.log 2>&1
```

---

## 📊 Dashboard Kullanımı

### Admin Panel

1. Admin panele giriş yap: `https://your-domain.com/admin/`
2. Dashboard'a git: Ana sayfada "Kuafora Dashboard" bölümü
3. Periyot seç: Günlük / Haftalık / Aylık / Yıllık / Tüm Zamanlar

### Gösterilen Metrikler:

- **DAU (Daily Active Users)**: O gün en az 1 kez giriş yapan benzersiz cihazlar
- **WAU (Weekly Active Users)**: Son 7 gün en az 1 kez giriş yapan
- **MAU (Monthly Active Users)**: Son 30 gün en az 1 kez giriş yapan
- **YAU (Yearly Active Users)**: Son 365 gün en az 1 kez giriş yapan
- **Tüm Zamanlar**: Hiç en az 1 kez giriş yapan toplam kullanıcılar

### Yüzdeler:

- **Retention Rate**: Son 7 günde kayıt olup hala aktif olan kullanıcı yüzdesi
- **Churn Rate**: Son 30 günde kayıt olup son 7 günde giriş yapmayan kullanıcı yüzdesi
- **Conversion Rate**: Son 30 günde kayıt olup aktif kullanıcıya dönüşen yüzdesi

---

## 🔍 Troubleshooting

### Problem: Dashboard'da aktif kullanıcılar 0 görünüyor

**Çözüm 1:** UserActivityLog'da veri olduğundan emin olun

```bash
docker exec -it kuafora-backend python manage.py shell
```

```python
from app.analytics.models import UserActivityLog
from datetime import date

# Bugün için kayıt var mı?
today_logs = UserActivityLog.objects.filter(activity_date=date.today())
print(f"Today's logs: {today_logs.count()}")

# Varsa, bazı kayıtları göster
for log in today_logs[:5]:
    print(f"User: {log.user}, Device: {log.device_id}, Count: {log.login_count}")
```

**Çözüm 2:** API endpoint'lerinize tracking ekleyin (yukarıdaki örneklere bakın)

**Çözüm 3:** Manuel test tracking

```python
from app.analytics.utils import track_login
from app.users.models import User

# Test kullanıcısı ile tracking yap
user = User.objects.filter(is_staff=False).first()
if user:
    track_login(
        user=user,
        device_id='test_device_123',
        app_type='main',
        platform='iOS'
    )
    print("✓ Test tracking created!")
```

### Problem: Migrations hatası

```bash
# Migrations sıfırla ve tekrar oluştur
docker exec -it kuafora-backend bash
python manage.py migrate analytics zero
python manage.py makemigrations analytics
python manage.py migrate analytics
```

### Problem: Import hatası

Eğer import hataları alıyorsanız, container'ı yeniden başlatın:

```bash
docker-compose restart backend
```

---

## 📱 Mobil Uygulama Gereksinimleri

Mobil uygulama her login/authentication isteğinde şu bilgileri **mutlaka** göndermelidir:

```json
{
  "email": "user@example.com",
  "password": "...",
  "device_id": "UUID veya cihaz unique identifier",
  "platform": "iOS" | "Android",
  "app_version": "1.0.0",
  "os_version": "17.0"
}
```

### iOS Örnek (Swift):

```swift
let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
let platform = "iOS"
let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
let osVersion = UIDevice.current.systemVersion

let loginData = [
    "email": email,
    "password": password,
    "device_id": deviceId,
    "platform": platform,
    "app_version": appVersion,
    "os_version": osVersion
]
```

### Android Örnek (Kotlin):

```kotlin
val deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
val platform = "Android"
val appVersion = BuildConfig.VERSION_NAME
val osVersion = Build.VERSION.RELEASE

val loginData = mapOf(
    "email" to email,
    "password" to password,
    "device_id" to deviceId,
    "platform" to platform,
    "app_version" to appVersion,
    "os_version" to osVersion
)
```

---

## 🎓 Nasıl Çalışır?

### 1. Kullanıcı Giriş Yapar

```
Mobil App → API Login Endpoint → track_login() → UserActivityLog + UserSession
```

### 2. Günlük Metrics Hesaplanır

```
Cron Job (01:00) → calculate_daily_metrics → DailyMetrics kaydı oluşturulur
```

### 3. Dashboard Gösterir

```
Admin Dashboard → UserActivityLog + DailyMetrics → Grafikler ve metrikler
```

---

## 📈 Gelecek Geliştirmeler

- [ ] Real-time dashboard (WebSocket ile canlı güncellemeler)
- [ ] Kullanıcı segmentasyonu (yeni/dönen kullanıcılar)
- [ ] Cohort analizi
- [ ] Funnel tracking
- [ ] A/B test metrics
- [ ] Push notification effectiveness tracking

---

## 🆘 Destek

Sorularınız için:
- Backend Lead Developer: [İletişim Bilgisi]
- Dokümantasyon: Bu dosya
- Admin Panel: https://your-domain.com/admin/

---

## ✅ Checklist

Kurulumu tamamladıktan sonra bu listeyi kontrol edin:

- [ ] Migrations uygulandı (`makemigrations` ve `migrate`)
- [ ] Admin panelde yeni modeller görünüyor (UserActivityLog, DailyMetrics)
- [ ] Login endpoint'lerine `track_login()` eklendi
- [ ] Mobil app `device_id` gönderiyor
- [ ] Manuel test tracking çalıştı
- [ ] Dashboard'da aktif kullanıcı sayıları görünüyor (0 değilse)
- [ ] Cron job kuruldu (günlük metrics için)
- [ ] `calculate_daily_metrics` command çalıştırıldı
- [ ] DailyMetrics tablosunda veriler var

---

**Son Güncelleme:** 2026-02-12
**Versiyon:** 1.0
