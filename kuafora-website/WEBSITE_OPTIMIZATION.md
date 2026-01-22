# Website Optimizasyonu ve S3 Yükleme Rehberi

## ✅ Yapılan Optimizasyonlar

### 1. SEO İyileştirmeleri
- ✅ Meta description ve keywords eklendi
- ✅ Open Graph (Facebook) meta tags eklendi
- ✅ Twitter Card meta tags eklendi
- ✅ Canonical URL eklendi
- ✅ Geo-location meta tags eklendi
- ✅ Robots meta tag eklendi

### 2. Performans İyileştirmeleri
- ✅ Font loading optimizasyonu (lazy load)
- ✅ CSS lazy loading
- ✅ Script defer attribute
- ✅ Preload critical resources
- ✅ Image lazy loading hazırlığı

### 3. Bug Düzeltmeleri
- ✅ Mobile menu toggle düzeltildi
- ✅ Console.error'lar production'da kaldırıldı
- ✅ Animation performance iyileştirildi

## 📸 Gerekli Görseller

### Ana Website İçin Görseller

#### 1. Open Graph Image (og-image.jpg)
- **Boyut**: 1200x630px
- **Format**: JPG veya PNG
- **Konum**: `static/img/og-image.jpg`
- **İçerik**: Kuafora logosu + "Kuaförünü Keşfet" metni
- **Kullanım**: Facebook, LinkedIn paylaşımlarında görünecek

#### 2. Twitter Card Image (twitter-card.jpg)
- **Boyut**: 1200x675px (16:9)
- **Format**: JPG veya PNG
- **Konum**: `static/img/twitter-card.jpg`
- **İçerik**: Kuafora logosu + kısa açıklama
- **Kullanım**: Twitter paylaşımlarında görünecek

#### 3. Apple Touch Icon (apple-touch-icon.png)
- **Boyut**: 180x180px
- **Format**: PNG
- **Konum**: `static/img/apple-touch-icon.png`
- **İçerik**: Kuafora logosu (kare)
- **Kullanım**: iOS cihazlarda home screen'de görünecek

#### 4. Ana Sayfa Ekran Görüntüleri
- **Konum**: `static/img/screens/`
- **Gerekli Ekranlar**:
  - `home-screen.png` - Ana ekran (iPhone/Android)
  - `map-view.png` - Harita görünümü
  - `barbershop-detail.png` - Kuaför detay ekranı
  - `reviews.png` - Yorumlar ekranı
  - `favorites.png` - Favoriler ekranı
  - `search.png` - Arama ekranı

#### 5. Partner Uygulaması Ekran Görüntüleri
- **Konum**: `static/img/screens/partner/`
- **Gerekli Ekranlar**:
  - `dashboard.png` - Partner dashboard
  - `appointments.png` - Randevu yönetimi
  - `staff.png` - Personel yönetimi
  - `reviews.png` - Yorum yönetimi
  - `analytics.png` - İstatistikler

### Görsel Özellikleri
- **Format**: PNG (şeffaf arka plan için) veya JPG
- **Kalite**: Yüksek çözünürlük (Retina için 2x)
- **Boyut**: Maksimum 2MB (optimize edilmiş)
- **Renk Profili**: sRGB

## 🚀 S3 Yükleme Altyapısı

### 1. Gerekli Paketler
```bash
pip install boto3 django-storages
```

### 2. Settings.py Güncellemeleri
```python
# S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'kuafora-website')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'eu-west-1')
AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN', f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com')
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=31536000',
}
AWS_DEFAULT_ACL = 'public-read'
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = False

# Static files
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

# Media files
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
```

### 3. Environment Variables
```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_STORAGE_BUCKET_NAME=kuafora-website
AWS_S3_REGION_NAME=eu-west-1
AWS_S3_CUSTOM_DOMAIN=cdn.kuafora.com  # Optional: CloudFront domain
```

### 4. S3 Bucket Oluşturma
1. AWS Console'a giriş yap
2. S3 servisine git
3. "Create bucket" butonuna tıkla
4. Bucket adı: `kuafora-website`
5. Region: `eu-west-1` (veya tercih ettiğin)
6. Public access: **Block all public access** kapat (static files için)
7. Bucket policy ekle:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::kuafora-website/*"
        }
    ]
}
```

### 5. Görselleri S3'e Yükleme

#### Manuel Yükleme (AWS Console)
1. S3 bucket'a git
2. `static/img/` klasörü oluştur
3. Görselleri yükle:
   - `static/img/og-image.jpg`
   - `static/img/twitter-card.jpg`
   - `static/img/apple-touch-icon.png`
   - `static/img/screens/` klasörüne ekran görüntüleri

#### Komut Satırı ile Yükleme
```bash
# AWS CLI kurulumu
pip install awscli

# Yapılandırma
aws configure

# Görselleri yükle
aws s3 sync static/img/ s3://kuafora-website/static/img/ --acl public-read
```

#### Django Management Command ile Yükleme
```python
# management/commands/upload_static_to_s3.py
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Upload static files to S3'
    
    def handle(self, *args, **options):
        call_command('collectstatic', '--noinput')
        # Static files otomatik olarak S3'e yüklenecek
```

### 6. CloudFront CDN Kurulumu (Opsiyonel)
1. CloudFront servisine git
2. "Create Distribution" butonuna tıkla
3. Origin Domain: S3 bucket'ı seç
4. Viewer Protocol Policy: Redirect HTTP to HTTPS
5. Allowed HTTP Methods: GET, HEAD, OPTIONS
6. Price Class: Use only North America and Europe (daha ucuz)
7. Distribution oluştur
8. `AWS_S3_CUSTOM_DOMAIN` environment variable'ına CloudFront domain'i ekle

## 📋 Yapılacaklar Listesi

### Kullanıcıdan İstenen Görseller
1. ✅ Open Graph image (1200x630px)
2. ✅ Twitter Card image (1200x675px)
3. ✅ Apple Touch Icon (180x180px)
4. ✅ Ana uygulama ekran görüntüleri (6 adet)
5. ✅ Partner uygulama ekran görüntüleri (5 adet)

### Teknik Yapılacaklar
1. ✅ `boto3` ve `django-storages` paketlerini ekle
2. ✅ Settings.py'ye S3 konfigürasyonu ekle
3. ✅ Environment variables ekle
4. ✅ S3 bucket oluştur
5. ✅ Görselleri S3'e yükle
6. ✅ CloudFront CDN kur (opsiyonel)

## 🔍 Test Etme

### Local Test
```bash
# Static files'ı local'de test et
python manage.py collectstatic --noinput

# S3'e yükleme testi
python manage.py upload_static_to_s3
```

### Production Test
1. Website'i aç
2. Developer Tools > Network sekmesi
3. Görsellerin S3'ten yüklendiğini kontrol et
4. Open Graph test: https://www.opengraph.xyz/
5. Twitter Card test: https://cards-dev.twitter.com/validator

## 📝 Notlar

- **Görsel Optimizasyonu**: Tüm görselleri [TinyPNG](https://tinypng.com/) veya [Squoosh](https://squoosh.app/) ile optimize et
- **Lazy Loading**: Büyük görseller için `loading="lazy"` attribute'u kullan
- **WebP Format**: Modern tarayıcılar için WebP formatı kullan (daha küçük dosya boyutu)
- **CDN**: CloudFront kullanarak görselleri daha hızlı yükle

## 🐛 Bilinen Sorunlar ve Çözümler

### Sorun 1: Görseller yüklenmiyor
**Çözüm**: S3 bucket policy'yi kontrol et, public access'i aç

### Sorun 2: CORS hatası
**Çözüm**: S3 bucket CORS configuration ekle:
```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedOrigins": ["*"],
        "ExposeHeaders": []
    }
]
```

### Sorun 3: Static files yüklenmiyor
**Çözüm**: `collectstatic` komutunu çalıştır ve `STATICFILES_STORAGE` ayarını kontrol et

