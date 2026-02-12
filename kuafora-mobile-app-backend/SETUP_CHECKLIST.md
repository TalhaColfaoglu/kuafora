# 🚀 Active User Tracking - Setup Checklist

## Hızlı Kurulum (5 dakika)

### 1️⃣ Sunucuya Bağlan

```bash
ssh -i ~/Downloads/makas-deneme.pem ubuntu@3.122.14.242
cd ~/kuafora
```

### 2️⃣ Setup Script'i Çalıştır

```bash
# Script'i çalıştırılabilir yap
chmod +x kuafora-mobile-app-backend/setup_active_user_tracking.sh

# Setup'ı çalıştır
./kuafora-mobile-app-backend/setup_active_user_tracking.sh
```

Bu script otomatik olarak:
- ✅ Migrations oluşturur ve çalıştırır
- ✅ Yeni modelleri test eder
- ✅ Test tracking verisi oluşturur
- ✅ Son 7 günün metriklerini hesaplar
- ✅ Dashboard'u doğrular

### 3️⃣ Dashboard'u Kontrol Et

1. Admin panele giriş yap: https://your-domain.com/admin/
2. "Kuafora Dashboard" bölümüne git
3. Aktif kullanıcı metriklerinin görünüp görünmediğini kontrol et

---

## 📋 Manuel Kurulum (Detaylı)

Eğer otomatik script çalışmazsa, manuel olarak:

### Step 1: Migrations

```bash
docker exec -it kuafora-backend python manage.py makemigrations analytics
docker exec -it kuafora-backend python manage.py migrate analytics
```

### Step 2: Test Tracking

```bash
docker exec -it kuafora-backend python manage.py shell
```

```python
from app.analytics.utils import track_login
from app.users.models import User

user = User.objects.filter(is_staff=False).first()
if user:
    track_login(
        user=user,
        device_id='test_device_123',
        app_type='main',
        platform='iOS'
    )
    print("✓ Test tracking created!")

# Verify
from app.analytics.models import UserActivityLog
from datetime import date
print(f"Today's logs: {UserActivityLog.objects.filter(activity_date=date.today()).count()}")
```

### Step 3: Calculate Metrics

```bash
# Son 7 günü hesapla
docker exec -it kuafora-backend python manage.py calculate_daily_metrics --backfill 7

# Veya sadece dün
docker exec -it kuafora-backend python manage.py calculate_daily_metrics
```

### Step 4: Verify Dashboard

```bash
docker exec -it kuafora-backend python manage.py shell
```

```python
from app.analytics.models import UserActivityLog, DailyMetrics
from datetime import date

print("Today Active Devices:", UserActivityLog.objects.filter(
    activity_date=date.today(), app_type='main'
).values('device_id').distinct().count())

print("DailyMetrics Records:", DailyMetrics.objects.count())
```

---

## 🔧 API Entegrasyonu

### Option 1: Login Endpoint'e Ekle (ÖNERİLEN)

Mevcut login endpoint'inizi bulun ve şunu ekleyin:

```python
from app.analytics.utils import track_login

# Login başarılı olduktan sonra:
track_login(
    user=user,
    device_id=request.data.get('device_id'),
    app_type='main',
    request=request,
    platform=request.data.get('platform', 'unknown'),
    app_version=request.data.get('app_version', ''),
    os_version=request.data.get('os_version', '')
)
```

📖 Detaylı örnekler: `API_TRACKING_EXAMPLES.py`

### Option 2: Middleware (Otomatik - Her İstek)

⚠️ UYARI: Sadece düşük trafikli uygulamalar için

`settings.py` → `MIDDLEWARE` listesine ekle:

```python
MIDDLEWARE = [
    # ... diğer middleware'ler
    'app.analytics.middleware.ActivityTrackingMiddleware',  # En sona ekle
]
```

---

## ⏰ Cron Job Kurulumu

Günlük metrics otomatik hesaplansın:

```bash
# Crontab düzenle
crontab -e

# En alta şunu ekle (her gün sabah 01:00):
0 1 * * * docker exec kuafora-backend python manage.py calculate_daily_metrics >> /home/ubuntu/logs/daily_metrics.log 2>&1

# Logs klasörünü oluştur
mkdir -p /home/ubuntu/logs
```

---

## ✅ Verification Checklist

Kurulum tamamlandıktan sonra kontrol et:

- [ ] **Migrations OK**: `docker exec kuafora-backend python manage.py showmigrations analytics`
- [ ] **Models OK**: Admin panelde "User activity logs" ve "Daily metrics" görünüyor
- [ ] **Test Data OK**: UserActivityLog'da en az 1 kayıt var
- [ ] **Dashboard OK**: Admin dashboard'da aktif kullanıcı sayıları 0'dan farklı
- [ ] **API Tracking OK**: Login endpoint'e tracking eklendi
- [ ] **Cron Job OK**: `crontab -l` ile kontrol et
- [ ] **Mobil App OK**: device_id gönderiliyor

---

## 🐛 Troubleshooting

### Dashboard'da 0 görünüyor

```bash
# 1. UserActivityLog'da veri var mı?
docker exec -it kuafora-backend python manage.py shell -c "
from app.analytics.models import UserActivityLog
from datetime import date
print('Today logs:', UserActivityLog.objects.filter(activity_date=date.today()).count())
"

# 2. Yoksa, test tracking yap
docker exec -it kuafora-backend python manage.py shell -c "
from app.analytics.utils import track_login
from app.users.models import User
user = User.objects.filter(is_staff=False).first()
if user:
    track_login(user=user, device_id='test_123', app_type='main', platform='iOS')
    print('✓ Test tracking created')
"

# 3. Dashboard'u yeniden kontrol et
```

### Migrations hatası

```bash
# Reset migrations
docker exec -it kuafora-backend python manage.py migrate analytics zero
docker exec -it kuafora-backend python manage.py makemigrations analytics
docker exec -it kuafora-backend python manage.py migrate analytics
```

### Container yeniden başlat

```bash
docker-compose restart backend
```

---

## 📱 Mobil App Gereksinimleri

Mobil uygulama her login isteğinde **mutlaka** şunları göndermelidir:

```json
{
  "email": "user@example.com",
  "password": "***",
  "device_id": "UNIQUE-DEVICE-UUID",  // ← ZORUNLU
  "platform": "iOS" | "Android",       // ← ZORUNLU
  "app_version": "1.0.0",
  "os_version": "17.0"
}
```

**device_id** nereden gelir?
- iOS: `UIDevice.current.identifierForVendor?.uuidString`
- Android: `Settings.Secure.ANDROID_ID`

---

## 📊 Dashboard Metrikleri

Kurulum tamamlandığında dashboard'da şunlar görünecek:

### Aktif Kullanıcı Metrikleri
- **Günlük Aktif (DAU)**: O gün en az 1 kez giriş yapan cihazlar
- **Haftalık Aktif (WAU)**: Son 7 gün en az 1 kez giriş yapan
- **Aylık Aktif (MAU)**: Son 30 gün en az 1 kez giriş yapan  
- **Yıllık Aktif (YAU)**: Son 365 gün en az 1 kez giriş yapan
- **Tüm Zamanlar**: Hiç en az 1 kez giriş yapan toplam

### Pasif Kullanıcı Metrikleri
- **Son 1 Ayda Girmeyen**: Aktif ama 30 gündür giriş yapmayan
- **Hiç Giriş Yapmamış**: Kayıtlı ama hiç login olmamış

### Büyüme & Tutma Metrikleri
- **Retention Rate**: Kayıtlıların kaçı aktif kaldı (%)
- **Churn Rate**: Kaçı kullanmayı bıraktı (%)
- **Conversion Rate**: Kayıtlıların kaçı aktif kullanıcıya dönüştü (%)

---

## 🎯 Sonraki Adımlar

1. ✅ Kurulumu tamamla (bu checklist)
2. 📱 Mobil app'e device_id gönderimi ekle
3. 🔧 API endpoint'lerine tracking ekle
4. ⏰ Cron job kur
5. 📊 Dashboard'u izle
6. 🚀 Production'a deploy

---

## 📚 Dökümanlar

- 📖 **Detaylı Setup**: `ACTIVE_USER_TRACKING_SETUP.md`
- 💻 **API Örnekleri**: `API_TRACKING_EXAMPLES.py`
- 🔧 **Auto Setup**: `setup_active_user_tracking.sh`

---

## 🆘 Yardım

Sorun mu yaşıyorsun?

1. `ACTIVE_USER_TRACKING_SETUP.md` → Troubleshooting bölümü
2. `API_TRACKING_EXAMPLES.py` → Kod örnekleri
3. Admin panel → Analytics → User activity logs (veri kontrolü)
4. `docker logs kuafora-backend` → Hata logları

---

**✨ İyi şanslar!**

Kurulum tamamlandıktan sonra dashboard'da tüm metrikleri görebileceksiniz.
