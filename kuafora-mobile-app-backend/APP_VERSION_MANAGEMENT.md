# Uygulama Versiyon Yönetimi

Bu dokümantasyon, mobil uygulama versiyon kontrolü ve güncelleme yönetimi için backend endpoint'inin nasıl kullanılacağını açıklar.

## Kurulum

### 1. Migration'ları Çalıştırın

```bash
cd /Users/talhacolfaoglu/Desktop/backend-frontend/kuafora
docker compose exec backend python manage.py makemigrations core
docker compose exec backend python manage.py migrate core
```

### 2. Admin Panel'den Versiyon Ekleme

1. Django Admin'e giriş yapın: `https://api.kuafora.com/admin/`
2. **Core** bölümünden **App versions** seçeneğine gidin
3. **Add App version** butonuna tıklayın
4. Formu doldurun:
   - **Platform**: Android veya iOS seçin
   - **Version name**: Versiyon adı (örn: `1.0.0-internal.2`)
   - **Version code**: Build numarası (örn: `2`)
   - **Force update**: Zorunlu güncelleme mi? (checkbox)
   - **Min version code**: Bu build'den eski olanlar için zorunlu güncelleme (opsiyonel)
   - **Update message**: Kullanıcıya gösterilecek mesaj
   - **Play store URL**: Play Store linki (boş bırakılırsa default kullanılır)
   - **Is active**: Bu versiyon aktif mi? (checkbox)

## Kullanım Senaryoları

### Senaryo 1: Normal Güncelleme (Opsiyonel)

**Durum**: Yeni bir versiyon yayınlandı ama eski versiyonlar hala çalışabilir.

**Ayarlar**:
- `force_update`: ❌ (False)
- `min_version_code`: Boş bırakın

**Sonuç**: Kullanıcıya güncelleme popup'ı gösterilir ama "Daha Sonra" ile kapatabilir.

### Senaryo 2: Kritik Güncelleme (Zorunlu)

**Durum**: Güvenlik açığı veya kritik hata düzeltmesi var, eski versiyonlar kullanılmamalı.

**Ayarlar**:
- `force_update`: ✅ (True)
- `min_version_code`: Boş bırakın veya belirli bir build numarası

**Sonuç**: Kullanıcıya zorunlu güncelleme popup'ı gösterilir, dialog kapatılamaz.

### Senaryo 3: Belirli Build'den Eski Olanlar İçin Zorunlu

**Durum**: Build 3 yayınlandı, Build 1 ve 2 için zorunlu güncelleme istiyorsunuz ama Build 3+ için opsiyonel.

**Ayarlar**:
- `force_update`: ❌ (False)
- `min_version_code`: `3` (Build 3'ten eski olanlar için zorunlu)

**Sonuç**: 
- Build 1-2 kullanıcıları: Zorunlu güncelleme görür
- Build 3+ kullanıcıları: Opsiyonel güncelleme görür

## API Endpoint

**URL**: `/api/app/version-check/`  
**Method**: `GET`  
**Authentication**: Gerekli değil (public endpoint)

### Request Parameters

- `current_version` (string): Mevcut uygulama versiyonu (örn: "1.0.0-internal.2")
- `current_build` (int): Mevcut build numarası (örn: 2)
- `platform` (string): Platform ("android" veya "ios")

### Response Format

```json
{
  "update_available": true,
  "force_update": false,
  "latest_version": "1.0.0-internal.3",
  "update_message": "Yeni özellikler ve hata düzeltmeleri eklendi.",
  "play_store_url": "https://play.google.com/store/apps/details?id=com.kuafora.app"
}
```

### Örnek Request

```bash
curl "https://api.kuafora.com/api/app/version-check/?current_version=1.0.0-internal.1&current_build=1&platform=android"
```

## Örnek Kullanım Senaryoları

### Örnek 1: İlk Versiyon Ekleme

1. Admin panel'e gidin
2. **App versions** → **Add App version**
3. Formu doldurun:
   ```
   Platform: Android
   Version name: 1.0.0-internal.2
   Version code: 2
   Force update: ❌
   Update message: Yeni özellikler ve iyileştirmeler için uygulamayı güncelleyin.
   Is active: ✅
   ```
4. **Save** butonuna tıklayın

### Örnek 2: Kritik Güvenlik Güncellemesi

1. Yeni versiyon ekleyin:
   ```
   Platform: Android
   Version name: 1.0.0-internal.3
   Version code: 3
   Force update: ✅
   Update message: Güvenlik güncellemesi: Lütfen uygulamayı hemen güncelleyin.
   Min version code: 2  (Build 2 ve daha eski olanlar için zorunlu)
   Is active: ✅
   ```

2. Eski versiyonları pasif yapın (opsiyonel):
   - Build 2'yi bulun
   - **Is active** checkbox'ını kaldırın

### Örnek 3: Production Release

1. Production versiyonu ekleyin:
   ```
   Platform: Android
   Version name: 1.0.0
   Version code: 10
   Force update: ❌
   Update message: İlk production sürümü yayınlandı!
   Play store URL: https://play.google.com/store/apps/details?id=com.kuafora.app
   Is active: ✅
   ```

## Notlar

- **Version code her zaman artmalı**: Play Store versionCode'u kontrol eder, azalamaz
- **Aktif versiyon**: Sadece `is_active=True` olan versiyonlar kontrol edilir
- **En son versiyon**: En yüksek `version_code`'a sahip aktif versiyon kullanılır
- **Platform ayrımı**: Android ve iOS için ayrı versiyonlar yönetilir
- **Hata durumu**: Endpoint hata verse bile `update_available: false` döner, kullanıcıyı rahatsız etmez

## Test

Endpoint'i test etmek için:

```bash
# Güncelleme yok
curl "https://api.kuafora.com/api/app/version-check/?current_version=1.0.0-internal.2&current_build=2&platform=android"

# Güncelleme var (opsiyonel)
curl "https://api.kuafora.com/api/app/version-check/?current_version=1.0.0-internal.1&current_build=1&platform=android"

# Zorunlu güncelleme
curl "https://api.kuafora.com/api/app/version-check/?current_version=1.0.0-internal.1&current_build=1&platform=android"
# (Eğer admin panel'de force_update=True yapıldıysa)
```

## Sorun Giderme

### Endpoint çalışmıyor
- Migration'ların çalıştırıldığından emin olun
- Django admin'de AppVersion modelinin göründüğünü kontrol edin

### Güncelleme popup'ı gösterilmiyor
- Admin panel'de aktif bir versiyon olduğundan emin olun
- `is_active=True` olmalı
- `version_code` mevcut build'den yüksek olmalı

### Zorunlu güncelleme çalışmıyor
- `force_update=True` olduğundan emin olun
- Veya `min_version_code` değerinin doğru olduğunu kontrol edin
