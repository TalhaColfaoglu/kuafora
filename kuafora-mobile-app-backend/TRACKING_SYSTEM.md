# 📊 Tracking Sistemi - Kurulum ve Kullanım

## ✅ Tamamlanan İşlemler

### 1. Backend Tracking Sistemi
- ✅ **Yeni `analytics` app oluşturuldu**
- ✅ **4 Model oluşturuldu:**
  - `AppEvent`: Uygulama açılma/kapanma eventleri
  - `ScreenView`: Ekran görüntüleme tracking
  - `FeatureUsage`: Özellik kullanım tracking
  - `UserSession`: Oturum bilgileri ve süreleri

### 2. API Endpoint'leri
- ✅ `/api/analytics/tracking/batch/` - Toplu tracking verisi gönderme
- ✅ `/api/analytics/tracking/event/` - Tek event tracking
- ✅ `/api/analytics/tracking/screen/` - Ekran görüntüleme
- ✅ `/api/analytics/tracking/feature/` - Özellik kullanımı
- ✅ `/api/analytics/tracking/session/` - Oturum tracking
- ✅ `/api/analytics/analytics/dashboard/` - Admin dashboard metrikleri

### 3. Frontend Entegrasyonu
- ✅ **Ana Uygulama (kuafora-mobile-app-frontend):**
  - `AnalyticsService` oluşturuldu
  - App lifecycle tracking (açılma/kapanma)
  - `main.dart`'a entegre edildi
  
- ✅ **Partner Uygulaması (kuafora_vitrin_app):**
  - `AnalyticsService` oluşturuldu
  - App lifecycle tracking (açılma/kapanma)
  - `main.dart` ve `app.dart`'a entegre edildi

### 4. Admin Dashboard Güncellemeleri
- ✅ Tracking verileri dashboard'a eklendi
- ✅ Uygulama açılma sayıları gösteriliyor
- ✅ Ortalama oturum süresi gösteriliyor
- ✅ En çok görüntülenen ekranlar listeleniyor
- ✅ En çok kullanılan özellikler listeleniyor
- ✅ Eski "gelecekte eklenecek" notu kaldırıldı

## 📋 Yapılması Gerekenler

### 1. Migration Çalıştırma
```bash
cd kuafora/kuafora-mobile-app-backend
python manage.py makemigrations analytics
python manage.py migrate
```

### 2. Paket Yükleme (Frontend)
```bash
# Ana uygulama
cd kuafora-mobile-app-frontend
flutter pub get

# Partner uygulaması
cd kuafora_vitrin_app
flutter pub get
```

### 3. Ekran Görüntüleme Tracking (Opsiyonel - İleride)
Ekran görüntülemelerini otomatik track etmek için `NavigatorObserver` eklenebilir:
```dart
MaterialApp(
  navigatorObservers: [
    AnalyticsNavigatorObserver(),
  ],
  // ...
)
```

### 4. Özellik Kullanım Tracking (Manuel)
Önemli özelliklerde manuel tracking eklenebilir:
```dart
// Örnek: Favori ekleme
AnalyticsService().trackFeatureUsage(
  'favorite_toggle',
  metadata: {'barbershop_id': shopId},
  success: true,
);
```

## 📊 Toplanan Veriler

### App Events
- `app_open`: Uygulama açıldı
- `app_close`: Uygulama kapandı
- `app_background`: Uygulama arka plana gitti
- `app_foreground`: Uygulama ön plana geldi

### Screen Views
- Ekran adı (örn: `HomeScreen`, `BarberDetailScreen`)
- Görüntüleme süresi
- Metadata (barbershop_id, campaign_id vb.)

### Feature Usage
- `favorite_toggle`: Favori ekleme/çıkarma
- `review_create`: Yorum oluşturma
- `search`: Arama
- `filter`: Filtreleme
- `map_view`: Harita görünümü
- `appointment_create`: Randevu oluşturma
- `campaign_view`: Kampanya görüntüleme
- `chat_send`: Mesaj gönderme
- `profile_edit`: Profil düzenleme
- `settings_change`: Ayarlar değiştirme

### User Sessions
- Oturum başlangıç/bitiş zamanı
- Oturum süresi
- Görüntülenen ekran sayısı
- Toplam event sayısı
- Platform ve app versiyonu

## 🎯 Dashboard Metrikleri

Admin dashboard'da şu metrikler gösteriliyor:
- **Uygulama Açılma Sayıları:** Toplam, bugün, bu hafta, bu ay
- **Ortalama Oturum Süresi:** Dakika cinsinden
- **En Çok Görüntülenen Ekranlar:** Top 10
- **En Çok Kullanılan Özellikler:** Top 10
- **Aktif Kullanıcı Metrikleri:** Tracking verilerine göre güncellendi

## 🔒 Güvenlik

- Tracking endpoint'leri `AllowAny` permission kullanıyor (anonim kullanıcılar da tracking gönderebilir)
- Kullanıcı bilgisi varsa kaydediliyor, yoksa null olarak saklanıyor
- IP adresi ve user agent kaydediliyor (analiz için)
- Hassas veri (şifre, token vb.) tracking'e dahil edilmiyor

## 📈 Performans

- Batch tracking desteği (toplu gönderim)
- Async tracking (uygulama performansını etkilemez)
- Hata durumunda uygulama çalışmaya devam eder
- Database index'leri optimize edildi

