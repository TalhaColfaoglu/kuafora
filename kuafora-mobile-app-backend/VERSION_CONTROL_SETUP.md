# 📱 Mobil Uygulama Versiyon Kontrol Sistemi

## 🎯 Özellikler

### ✅ Tamamlanan İşlevler
1. **Versiyon Yönetimi**
   - Her iki uygulama için (Ana + Partner)
   - Her iki platform için (Android + iOS)
   - Admin panelinde renklendirme ve görsel iyileştirmeler
   - Dashboard'da canlı versiyon görüntüleme

2. **Zorunlu Güncelleme Sistemi**
   - `force_update`: Bu versiyondan eski tüm kullanıcılar güncellemek zorunda
   - `min_version_code`: Belirtilen build numarasından eski versiyonlar için zorunlu güncelleme
   - Özelleştirilebilir güncelleme mesajı (`update_message`)
   - Play Store / App Store URL yönlendirmesi

3. **API Endpoint**
   - `/api/app/version-check/` endpoint'i zaten mevcut ve çalışıyor
   - Query parametreleri: `current_version`, `current_build`, `platform`, `app_type`
   - Mobil app bu endpoint'e istek atarak güncelleme kontrolü yapabilir

4. **Admin Panel İyileştirmeleri**
   - Versiyon yönetimi için gelişmiş admin interface
   - Toplu işlemler: Aktif/Pasif etme, Zorunlu güncelleme ayarlama
   - Renklendirme ve ikonlar ile görsel arayüz

5. **Dashboard Organizasyonu**
   - Versiyon yönetimi dashboard'un en üstünde
   - Benzer veriler gruplandırıldı:
     * Aktif + Pasif kullanıcılar + Giriş sıklığı (tek section)
     * Kullanıcı istatistikleri + Kayıt metrikleri (tek section)
   - Daha temiz ve organize görünüm

## 📋 Kullanım

### 1. Yeni Versiyon Ekleme

**Admin Panel → Core → App versions → Add App version**

```
Platform: Android veya iOS seç
App Type: main (Ana Uygulama) veya partner (Partner Uygulaması) seç
Version Name: Örn: "1.2.3" veya "1.0.0-internal.5"
Version Code: Build numarası (her yeni build için artar, örn: 15)
Force Update: ✅ işaretle = Bu versiyondan eski TÜMÜ güncellemek zorunda
Min Version Code: Örn: 10 yazarsan → Build 10'dan eski olanlar güncellemek zorunda
Update Message: "Yeni özellikler ve hata düzeltmeleri ekledik, lütfen güncelleyin!"
Play Store URL: Boş bırakabilirsin (otomatik URL kullanılır)
Is Active: ✅ işaretli olmalı
```

### 2. Zorunlu Güncelleme Senaryoları

#### Senaryo A: Bu versiyondan eski TÜMÜ güncellesin
```
Version Code: 20
Force Update: ✅ (açık)
Min Version Code: (boş bırak)

Sonuç: Build 19, 18, 17... tüm eski versiyonlar güncellemek zorunda
```

#### Senaryo B: Sadece çok eski versiyonlar güncellesin
```
Version Code: 20
Force Update: ❌ (kapalı)
Min Version Code: 15

Sonuç: Build 14, 13, 12... sadece 15'ten eski olanlar güncellemek zorunda
Build 15, 16, 17, 18, 19 → İsteğe bağlı güncelleme gösterilir
```

#### Senaryo C: İsteğe bağlı güncelleme (tavsiye)
```
Version Code: 20
Force Update: ❌ (kapalı)
Min Version Code: (boş bırak)

Sonuç: Tüm kullanıcılara "güncelleme mevcut" mesajı gösterilir ama zorunlu değil
```

### 3. Mobil App Entegrasyonu

Mobil app şu endpoint'e istek atmalı:

```http
GET /api/app/version-check/?current_version=1.0.0&current_build=10&platform=android&app_type=main
```

**Response Örneği:**

```json
{
  "update_available": true,
  "force_update": true,
  "latest_version": "1.2.0",
  "update_message": "Yeni özellikler ve hata düzeltmeleri ekledik!",
  "play_store_url": "https://play.google.com/store/apps/details?id=com.kuafora.app"
}
```

**Mobil App Davranışı:**

- `force_update: true` → Popup göster, "Şimdi Güncelle" butonu, popup kapatılamaz
- `force_update: false` + `update_available: true` → "Güncelleme Mevcut" mesajı, "Daha Sonra" butonu var
- `update_available: false` → Hiçbir şey gösterme

### 4. Dashboard'da Versiyon Görüntüleme

**Admin Dashboard** (ilk section):
- 📱 Mobil Uygulama Versiyon Yönetimi
- 4 kart: Ana/Android, Ana/iOS, Partner/Android, Partner/iOS
- Zorunlu güncelleme ise **KIRMIZI** renk ve ⚠️ işareti
- Min version belirtilmişse **TURUNCU** badge

## 🔧 Teknik Detaylar

### Model: `AppVersion`
**Dosya:** `app/core/models.py`

```python
- platform: 'android' | 'ios'
- app_type: 'main' | 'partner'
- version_name: String (örn: "1.2.3")
- version_code: Integer (build numarası)
- force_update: Boolean
- min_version_code: Integer (opsiyonel)
- update_message: Text
- play_store_url: URL (opsiyonel)
- is_active: Boolean
```

### Admin Interface
**Dosya:** `app/core/admin.py`
- Renklendirme ve ikonlar
- Toplu işlemler (actions)
- Filtreleme ve arama

### API View
**Dosya:** `app/core/views.py`
**Endpoint:** `/api/app/version-check/`
**Method:** GET
**Permissions:** AllowAny (herkes erişebilir)

### Dashboard
**Dosya:** `app/users/admin_dashboard.py`, `templates/admin/dashboard.html`
- Versiyon bilgileri context'e eklendi
- Template'te versiyon kartları gösteriliyor

## 📊 Dashboard Organizasyonu (Yeni)

### Bölüm Sıralaması:
1. **📱 Mobil Uygulama Versiyon Yönetimi** (EN ÜST - YENİ)
2. **📅 Seçili Dönem Özeti**
3. **📈 Aktif & Pasif Kullanıcı Metrikleri + Giriş Sıklığı** (BİRLEŞTİRİLDİ)
   - ✅ Aktif Kullanıcılar (DAU/WAU/MAU/YAU)
   - 🔄 Kullanıcı Giriş Sıklığı (günlük/haftalık/aylık ortalama)
   - ⚠️ Pasif Kullanıcılar
4. **👥 Kullanıcı Genel İstatistikleri & Kayıt Bilgileri** (BİRLEŞTİRİLDİ)
   - 👤 Genel Kullanıcı Bilgileri
   - 📝 Kayıt Metrikleri
5. **📊 Büyüme & Tutma Metrikleri**
6. **💬 Kullanıcı Etkileşim Metrikleri**
7. **👥 Cinsiyet Dağılımı**
8. **📍 En Çok Kullanıcı Olan Şehirler**
9. **⭐ En Aktif Kullanıcılar + 🔥 En Sık Giriş Yapanlar**
10. **💇 Barbershop İstatistikleri**
11. **📅 Randevu İstatistikleri**
12. **🗺️ Kullanım İstatistikleri**
13. **📧 E-posta İstatistikleri**

### İyileştirmeler:
- ✅ Benzer veriler yan yana gruplandırıldı
- ✅ Alt başlıklar eklendi (renklendirme ile)
- ✅ Daha az main section (3 section birleştirildi)
- ✅ Daha temiz ve organize görünüm

## 🚀 Kurulum ve Test

### 1. Sunucuda Güncelleme

```bash
# Git pull
cd ~/kuafora-mobile-app-backend
git pull

# Docker rebuild
docker compose build backend backend_dev
docker compose up -d backend backend_dev

# Migrationları uygula
docker exec kuafora_backend python manage.py migrate
docker exec kuafora_backend_dev python manage.py migrate

# Servisleri restart et
docker compose restart backend backend_dev
```

### 2. Admin Panelden İlk Versiyon Ekle

1. Admin panel'e gir: https://your-domain.com/admin/
2. **Core → App versions** bölümüne git
3. **Add App version** butonuna tıkla
4. Bilgileri doldur (yukarıdaki örneklere bak)
5. **Save** et

### 3. Dashboard'u Kontrol Et

1. **Admin** ana sayfasına git
2. **📊 Kuafora Analytics Dashboard** açılacak
3. En üstte **📱 Mobil Uygulama Versiyon Yönetimi** bölümünü gör
4. Versiyon kartlarının göründüğünü doğrula

### 4. API Test Et

```bash
# Test komutu (sunucuda)
curl "http://localhost:8000/api/app/version-check/?current_version=1.0.0&current_build=1&platform=android&app_type=main"
```

**Beklenen Çıktı:**
```json
{
  "update_available": true,
  "force_update": false,
  "latest_version": "...",
  "update_message": "...",
  "play_store_url": "..."
}
```

## 💡 İpuçları

1. **Her platform için ayrı versiyon ekle:** Android ve iOS versiyonları genelde farklı olur
2. **Her uygulama için ayrı versiyon:** Ana uygulama ve Partner uygulaması ayrı yönetilir
3. **Build numaraları her zaman artmalı:** 15 → 16 → 17...
4. **Zorunlu güncellemeyi dikkatli kullan:** Kullanıcı deneyimini etkileyebilir
5. **Test et:** Önce test ortamında dene, sonra production'a al

## 📞 Destek

Sorun yaşarsan:
1. Admin panel loglarını kontrol et
2. API endpoint'i test et
3. Dashboard'da versiyon kartlarının göründüğünü doğrula
4. Mobil app loglarını kontrol et

## ✅ Tamamlananlar

- [x] AppVersion modeli zaten mevcut ve çalışıyor
- [x] Admin paneli geliştirildi (renklendirme, actions)
- [x] Dashboard'a versiyon yönetimi bölümü eklendi
- [x] Dashboard organize edildi (benzer veriler yan yana)
- [x] API endpoint çalışıyor
- [x] Dokümantasyon hazırlandı

## 📱 Mobil App Yapılacaklar

Mobil app geliştirici tarafından:
1. App başlangıcında version check API'sine istek at
2. Response'a göre popup göster:
   - `force_update: true` → Kapatılamaz popup, "Şimdi Güncelle" butonu
   - `force_update: false` + `update_available: true` → Kapatılabilir popup, "Daha Sonra" butonu
3. "Şimdi Güncelle" butonuna tıklanınca → `play_store_url`'ye yönlendir

## 🎉 Sonuç

Artık:
- ✅ Admin panelinden her iki uygulama için versiyon yönetimi yapabilirsin
- ✅ Zorunlu güncelleme ayarlayabilirsin
- ✅ Dashboard'da tüm versiyonları görebilirsin
- ✅ Mobil app API'den versiyon kontrolü yapabilir
- ✅ Dashboard daha organize ve temiz

**Kullanıcı deneyimi:**
Kullanıcılar uygulamayı açtığında, eğer zorunlu güncelleme varsa önce güncellemek zorunda kalacak. İsteğe bağlı güncelleme varsa "Daha Sonra" diyebilecek.
