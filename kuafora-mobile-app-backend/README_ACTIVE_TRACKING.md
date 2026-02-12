# 🎯 Aktif Kullanıcı Tracking Sistemi

> Admin dashboard'da aktif kullanıcı metriklerini (DAU, WAU, MAU, YAU) doğru göstermek için kapsamlı tracking sistemi

---

## 🚀 Hızlı Başlangıç (2 Dakika)

### 1. Sunucuya Bağlan

```bash
ssh -i ~/Downloads/makas-deneme.pem ubuntu@3.122.14.242
cd ~/kuafora
```

### 2. Setup Script'i Çalıştır

```bash
chmod +x kuafora-mobile-app-backend/setup_active_user_tracking.sh
./kuafora-mobile-app-backend/setup_active_user_tracking.sh
```

### 3. Dashboard'u Kontrol Et

https://your-domain.com/admin/ → "Kuafora Dashboard"

✅ Aktif kullanıcı metrikleri artık görünüyor olmalı!

---

## 📚 Dokümantasyon

| Dosya | Ne Zaman Kullanılır |
|-------|---------------------|
| **[SETUP_CHECKLIST.md](./SETUP_CHECKLIST.md)** | ⭐ İLK BAŞLANGIÇ - Adım adım kurulum |
| **[CHANGES_SUMMARY.md](./CHANGES_SUMMARY.md)** | 📝 Ne değişti, nasıl çalışıyor |
| **[API_TRACKING_EXAMPLES.py](./API_TRACKING_EXAMPLES.py)** | 💻 API endpoint'lere tracking ekleme |
| **[ACTIVE_USER_TRACKING_SETUP.md](./ACTIVE_USER_TRACKING_SETUP.md)** | 📖 Detaylı teknik döküman |

---

## ❓ Sık Sorulan Sorular

### Dashboard'da hala 0 görünüyor?

1. Setup script'i çalıştırdınız mı?
   ```bash
   ./setup_active_user_tracking.sh
   ```

2. UserActivityLog'da veri var mı?
   ```bash
   docker exec kuafora-backend python manage.py shell -c "
   from app.analytics.models import UserActivityLog
   print('Count:', UserActivityLog.objects.count())
   "
   ```

3. Yoksa, test tracking yapın:
   ```bash
   docker exec kuafora-backend python manage.py shell -c "
   from app.analytics.utils import track_login
   from app.users.models import User
   user = User.objects.filter(is_staff=False).first()
   if user:
       track_login(user=user, device_id='test', app_type='main', platform='iOS')
   "
   ```

📖 Daha fazla troubleshooting: [SETUP_CHECKLIST.md](./SETUP_CHECKLIST.md#-troubleshooting)

### API endpoint'lere nasıl tracking eklerim?

```python
from app.analytics.utils import track_login

@api_view(['POST'])
def login_view(request):
    user = authenticate(...)
    
    # ✅ Tracking ekle
    track_login(
        user=user,
        device_id=request.data.get('device_id'),
        app_type='main',
        request=request
    )
    
    return Response({'token': token})
```

💻 Daha fazla örnek: [API_TRACKING_EXAMPLES.py](./API_TRACKING_EXAMPLES.py)

### Mobil app ne göndermeli?

Her login isteğinde:

```json
{
  "email": "user@example.com",
  "password": "***",
  "device_id": "UNIQUE-UUID",  // ← ZORUNLU
  "platform": "iOS",           // ← ZORUNLU
  "app_version": "1.0.0",
  "os_version": "17.0"
}
```

### Günlük metrics otomatik hesaplansın mı?

Evet! Cron job ekleyin:

```bash
crontab -e

# Her gün 01:00'de
0 1 * * * docker exec kuafora-backend python manage.py calculate_daily_metrics
```

### Migration hatası alıyorum?

```bash
# Reset ve tekrar
docker exec kuafora-backend python manage.py migrate analytics zero
docker exec kuafora-backend python manage.py makemigrations analytics
docker exec kuafora-backend python manage.py migrate analytics
```

---

## 📊 Dashboard Metrikleri

Kurulum sonrası dashboard'da görünecek:

### Aktif Kullanıcılar
- ✅ **Günlük Aktif (DAU)**: O gün giriş yapanlar
- ✅ **Haftalık Aktif (WAU)**: Son 7 günde giriş yapanlar
- ✅ **Aylık Aktif (MAU)**: Son 30 günde giriş yapanlar
- ✅ **Yıllık Aktif (YAU)**: Son 365 günde giriş yapanlar
- ✅ **Tüm Zamanlar**: Hiç giriş yapmış toplam

### Retention/Churn
- ✅ **Retention Rate**: Kayıtlıların aktif kalma oranı
- ✅ **Churn Rate**: Ayrılma oranı
- ✅ **Conversion Rate**: Dönüşüm oranı

### Grafikler
- ✅ Son 7 günlük kayıt trendi
- ✅ Son 30 günlük aktif kullanıcı trendi
- ✅ Haftalık karşılaştırma

---

## 🔧 Manuel Kurulum

Otomatik script çalışmazsa:

### 1. Migrations

```bash
docker exec kuafora-backend python manage.py makemigrations analytics
docker exec kuafora-backend python manage.py migrate analytics
```

### 2. Test Tracking

```bash
docker exec kuafora-backend python manage.py shell
```

```python
from app.analytics.utils import track_login
from app.users.models import User

user = User.objects.filter(is_staff=False).first()
track_login(user=user, device_id='test_123', app_type='main', platform='iOS')
```

### 3. Calculate Metrics

```bash
docker exec kuafora-backend python manage.py calculate_daily_metrics --backfill 7
```

### 4. Verify

Admin panel → Analytics → User activity logs → Veri var mı kontrol et

---

## 🎯 Ne Değişti?

### Yeni Özellikler ✨

- ✅ **Otomatik Tracking**: Kullanıcı her giriş yaptığında track ediliyor
- ✅ **Doğru Metrikler**: Dashboard gerçek verileri gösteriyor
- ✅ **Tarihsel Veri**: Günlük snapshots saklanıyor
- ✅ **Tüm Zamanlar**: All-time metrikleri eklendi
- ✅ **Kolay Entegrasyon**: Tek satır kod ile tracking

### Yeni Database Tabloları 🗄️

- `analytics_user_activity_log`: Günlük kullanıcı girişleri
- `analytics_daily_metrics`: Günlük metric snapshot'ları

### Güncellenen Dosyalar 📝

- `app/analytics/models.py`: 2 yeni model
- `app/analytics/admin.py`: Admin interface
- `app/users/admin_dashboard.py`: Doğru metrik hesaplamaları
- + 4 yeni utility/signal dosyası

📖 Detaylar: [CHANGES_SUMMARY.md](./CHANGES_SUMMARY.md)

---

## ✅ Verification Checklist

Kurulum sonrası kontrol edin:

- [ ] `setup_active_user_tracking.sh` çalıştırıldı ✅
- [ ] Migrations uygulandı (`migrate analytics`)
- [ ] Test tracking oluşturuldu
- [ ] UserActivityLog'da veri var
- [ ] Dashboard'da aktif kullanıcılar görünüyor
- [ ] Login endpoint'e tracking eklendi
- [ ] Mobil app device_id gönderiyor
- [ ] Cron job kuruldu (günlük metrics için)

---

## 🆘 Yardım

Sorun mu yaşıyorsunuz?

1. 📋 [SETUP_CHECKLIST.md](./SETUP_CHECKLIST.md) → Troubleshooting
2. 💻 [API_TRACKING_EXAMPLES.py](./API_TRACKING_EXAMPLES.py) → Kod örnekleri
3. 📖 [ACTIVE_USER_TRACKING_SETUP.md](./ACTIVE_USER_TRACKING_SETUP.md) → Detaylı döküman
4. 🐛 `docker logs kuafora-backend` → Hata logları

---

## 🎓 Nasıl Çalışır?

```
┌─────────────┐
│  Mobil App  │
└──────┬──────┘
       │ Login (device_id)
       ▼
┌─────────────────┐
│  API Endpoint   │
│  track_login()  │
└──────┬──────────┘
       │
       ▼
┌──────────────────────┐    ┌────────────────┐
│ UserActivityLog      │    │  UserSession   │
│ (günlük aktivite)    │    │  (oturum)      │
└──────────────────────┘    └────────────────┘
       │
       ▼
┌──────────────────────┐
│  Management Command  │
│  (daily cron job)    │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│   DailyMetrics       │
│   (snapshot)         │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Admin Dashboard     │
│  (metrikleri göster) │
└──────────────────────┘
```

---

## 📞 İletişim

Sorularınız için:
- **Kurulum**: Bu dökümanlar
- **Teknik**: [ACTIVE_USER_TRACKING_SETUP.md](./ACTIVE_USER_TRACKING_SETUP.md)
- **API**: [API_TRACKING_EXAMPLES.py](./API_TRACKING_EXAMPLES.py)

---

## 🎉 Başarılar!

Kurulumu tamamladıktan sonra admin dashboard'da tüm kullanıcı metriklerini görebileceksiniz.

**İyi çalışmalar! 🚀**

---

**Son Güncelleme:** 2026-02-12  
**Versiyon:** 1.0.0  
**Durum:** ✅ Kuruluma Hazır
