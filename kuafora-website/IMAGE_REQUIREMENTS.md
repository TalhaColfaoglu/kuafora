# Görsel Gereksinimleri ve Yükleme Rehberi

## 📸 İhtiyaç Duyulan Görseller

### 1. SEO ve Social Media Görselleri

#### Open Graph Image (og-image.jpg)
- **Boyut**: 1200x630px (1.91:1 oran)
- **Format**: JPG (optimize edilmiş)
- **Maksimum Boyut**: 1MB
- **Konum**: `static/img/og-image.jpg`
- **İçerik Önerisi**:
  - Kuafora logosu (sol üst)
  - "Kuaförünü Keşfet" başlığı
  - Uygulama mockup'ı veya harita görseli
  - Arka plan: Beyaz veya açık gri gradient

#### Twitter Card Image (twitter-card.jpg)
- **Boyut**: 1200x675px (16:9 oran)
- **Format**: JPG (optimize edilmiş)
- **Maksimum Boyut**: 1MB
- **Konum**: `static/img/twitter-card.jpg`
- **İçerik Önerisi**:
  - Kuafora logosu (merkez)
  - Kısa açıklama metni
  - Uygulama özellikleri ikonları

#### Apple Touch Icon (apple-touch-icon.png)
- **Boyut**: 180x180px
- **Format**: PNG (şeffaf arka plan)
- **Konum**: `static/img/apple-touch-icon.png`
- **İçerik**: Kuafora logosu (kare, merkezde)

### 2. Ana Uygulama Ekran Görüntüleri

Tüm ekran görüntüleri **iPhone 14 Pro** veya **Samsung Galaxy S23** boyutunda olmalı.

#### Home Screen (home-screen.png)
- **Boyut**: 1170x2532px (iPhone 14 Pro) veya 1080x2340px (Android)
- **Format**: PNG
- **Konum**: `static/img/screens/home-screen.png`
- **İçerik**: Ana sayfa - kuaför listesi, arama çubuğu, filtreler

#### Map View (map-view.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/map-view.png`
- **İçerik**: Harita görünümü - kuaförler harita üzerinde pin'lerle

#### Barbershop Detail (barbershop-detail.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/barbershop-detail.png`
- **İçerik**: Kuaför detay sayfası - fotoğraflar, yorumlar, çalışma saatleri

#### Reviews (reviews.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/reviews.png`
- **İçerik**: Yorumlar listesi - kullanıcı yorumları, puanlar

#### Favorites (favorites.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/favorites.png`
- **İçerik**: Favoriler sayfası - kaydedilmiş kuaförler

#### Search (search.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/search.png`
- **İçerik**: Arama sonuçları - filtreler, sonuç listesi

### 3. Partner Uygulaması Ekran Görüntüleri

#### Dashboard (dashboard.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/partner/dashboard.png`
- **İçerik**: Partner dashboard - istatistikler, hızlı erişim

#### Appointments (appointments.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/partner/appointments.png`
- **İçerik**: Randevu yönetimi - takvim görünümü, randevu listesi

#### Staff (staff.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/partner/staff.png`
- **İçerik**: Personel yönetimi - personel listesi, çalışma saatleri

#### Reviews Management (reviews.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/partner/reviews.png`
- **İçerik**: Yorum yönetimi - yorumlar listesi, yanıt verme

#### Analytics (analytics.png)
- **Boyut**: 1170x2532px veya 1080x2340px
- **Format**: PNG
- **Konum**: `static/img/screens/partner/analytics.png`
- **İçerik**: İstatistikler - gelir grafikleri, performans metrikleri

## 🎨 Görsel Tasarım Kılavuzu

### Renkler
- **Primary**: #0A0A0A (Siyah)
- **Accent Rose**: #F43F5E
- **Accent Violet**: #8B5CF6
- **Accent Emerald**: #10B981
- **Accent Amber**: #F59E0B
- **Accent Sky**: #0EA5E9

### Tipografi
- **Display Font**: Cabinet Grotesk (başlıklar)
- **Body Font**: Satoshi (metin)

### Stil
- Modern, minimal tasarım
- Yumuşak gölgeler
- Yuvarlatılmış köşeler (border-radius: 12-24px)
- Gradient arka planlar (opsiyonel)

## 📤 Görselleri Yükleme

### Yöntem 1: Manuel Yükleme (AWS Console)
1. AWS Console'a giriş yap
2. S3 servisine git
3. `kuafora-website` bucket'ını aç
4. `static/img/` klasörüne git
5. Görselleri sürükle-bırak ile yükle
6. Her görsel için "Make public" seçeneğini işaretle

### Yöntem 2: AWS CLI ile Yükleme
```bash
# AWS CLI kurulumu
pip install awscli

# Yapılandırma
aws configure
# AWS Access Key ID: [gir]
# AWS Secret Access Key: [gir]
# Default region: eu-west-1
# Default output format: json

# Görselleri yükle
aws s3 cp static/img/og-image.jpg s3://kuafora-website/static/img/og-image.jpg --acl public-read
aws s3 cp static/img/twitter-card.jpg s3://kuafora-website/static/img/twitter-card.jpg --acl public-read
aws s3 cp static/img/apple-touch-icon.png s3://kuafora-website/static/img/apple-touch-icon.png --acl public-read

# Tüm ekran görüntülerini yükle
aws s3 sync static/img/screens/ s3://kuafora-website/static/img/screens/ --acl public-read
```

### Yöntem 3: Django Management Command
```bash
# Static files'ı topla ve S3'e yükle
python manage.py collectstatic --noinput
```

## ✅ Kontrol Listesi

### Görsel Hazırlığı
- [ ] Open Graph image hazır (1200x630px)
- [ ] Twitter Card image hazır (1200x675px)
- [ ] Apple Touch Icon hazır (180x180px)
- [ ] Ana uygulama ekran görüntüleri hazır (6 adet)
- [ ] Partner uygulama ekran görüntüleri hazır (5 adet)

### Optimizasyon
- [ ] Tüm görseller optimize edildi (TinyPNG veya Squoosh)
- [ ] Dosya boyutları kontrol edildi (<2MB)
- [ ] Görsel kalitesi kontrol edildi (Retina için yeterli)

### Yükleme
- [ ] S3 bucket oluşturuldu
- [ ] Görseller S3'e yüklendi
- [ ] Public access ayarları yapıldı
- [ ] URL'ler test edildi

### Test
- [ ] Website'de görseller görünüyor
- [ ] Open Graph test edildi (https://www.opengraph.xyz/)
- [ ] Twitter Card test edildi (https://cards-dev.twitter.com/validator)
- [ ] Mobile'da görseller düzgün görünüyor

## 🔗 Faydalı Linkler

- **Görsel Optimizasyonu**: https://tinypng.com/ veya https://squoosh.app/
- **Open Graph Test**: https://www.opengraph.xyz/
- **Twitter Card Validator**: https://cards-dev.twitter.com/validator
- **Facebook Sharing Debugger**: https://developers.facebook.com/tools/debug/

## 📝 Notlar

- Tüm görselleri **sRGB** renk profili ile kaydet
- Ekran görüntüleri için **PNG** formatı kullan (şeffaf arka plan için)
- Social media görselleri için **JPG** formatı kullan (daha küçük dosya boyutu)
- Görselleri yüklerken **lazy loading** kullan (performans için)
- **WebP** formatı da destekleniyor (modern tarayıcılar için)

