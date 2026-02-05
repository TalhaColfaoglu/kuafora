# CloudFront CDN Kurulumu - Kuafora Website

Bu doküman, Kuafora website görsellerinin CloudFront CDN üzerinden yüklenmesi için gerekli adımları açıklar.

## 🎯 CloudFront Nedir ve Neden Kullanmalıyız?

CloudFront, AWS'in içerik dağıtım ağıdır (CDN). Görselleri CloudFront üzerinden yüklemek:
- **Daha hızlı yükleme**: Görseller kullanıcıya en yakın edge location'dan servis edilir
- **Daha düşük maliyet**: S3'ten direkt yükleme yerine CloudFront cache kullanılır
- **Daha iyi performans**: Özellikle global kullanıcılar için gecikme süresi azalır
- **Otomatik HTTPS**: CloudFront SSL sertifikası sağlar

## 📋 Önkoşullar

1. ✅ S3 bucket oluşturulmuş ve görseller yüklenmiş olmalı
2. ✅ AWS hesabı ve IAM yetkileri
3. ✅ Django settings'te S3 yapılandırması aktif

## 🚀 CloudFront Distribution Oluşturma

### Adım 1: CloudFront Console'a Git

1. AWS Console'da **CloudFront** servisine git
2. **Create Distribution** butonuna tıkla

### Adım 2: Origin Ayarları

**Origin Domain:**
- S3 bucket'ınızı seçin (örn: `kuafora-website.s3.eu-central-1.amazonaws.com`)
- VEYA direkt bucket adını yazın: `kuafora-website`

**Origin Path:** Boş bırakın (tüm bucket içeriği için)

**Origin Access:**
- **Origin Access Control Settings (Recommended)** seçin
- **Create control setting** ile yeni bir OAC oluşturun:
  - Name: `kuafora-website-oac`
  - Signing behavior: `Sign requests (recommended)`
  - Origin type: `S3`

### Adım 3: Default Cache Behavior

**Viewer Protocol Policy:**
- ✅ **Redirect HTTP to HTTPS** (önerilen)

**Allowed HTTP Methods:**
- ✅ **GET, HEAD, OPTIONS** (static files için yeterli)

**Cache Policy:**
- **CachingOptimized** veya **CachingDisabled** (geliştirme için)
- Production için özel cache policy oluşturabilirsiniz:
  ```json
  {
    "MinTTL": 86400,
    "MaxTTL": 31536000,
    "DefaultTTL": 86400
  }
  ```

**Compress Objects Automatically:** ✅ **Yes** (görseller için önemli)

### Adım 4: Distribution Settings

**Price Class:**
- **Use only North America and Europe** (daha ucuz)
- VEYA **Use all edge locations** (en hızlı, daha pahalı)

**Alternate Domain Names (CNAMEs):** (Opsiyonel)
- Eğer custom domain kullanacaksanız: `cdn.kuafora.com`
- SSL sertifikası için AWS Certificate Manager'da sertifika oluşturun

**SSL Certificate:**
- **Default CloudFront Certificate** (ücretsiz)
- VEYA **Custom SSL Certificate** (custom domain için)

**Default Root Object:** Boş bırakın

### Adım 5: Distribution Oluştur

1. **Create Distribution** butonuna tıkla
2. Distribution oluşturulması 10-15 dakika sürebilir
3. **Status** "Deployed" olduğunda hazır

## 🔧 Django Settings Yapılandırması

### Environment Variable Ekleme

Production environment variable'larına ekleyin:

```bash
# CloudFront Distribution Domain
AWS_S3_CUSTOM_DOMAIN=d1234567890abc.cloudfront.net
```

VEYA custom domain kullanıyorsanız:

```bash
AWS_S3_CUSTOM_DOMAIN=cdn.kuafora.com
```

### Settings.py Kontrolü

`config/settings.py` dosyasında zaten CloudFront desteği var:

```python
# S3 Configuration
AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN')

# Use S3 for static files if credentials are provided
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    if AWS_S3_CUSTOM_DOMAIN:
        # CloudFront domain kullanılıyor
        STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    else:
        # Direkt S3 kullanılıyor
        STATIC_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/'
```

## 🔐 S3 Bucket Policy Güncelleme (Origin Access Control için)

CloudFront OAC kullanıyorsanız, S3 bucket policy'yi güncelleyin:

1. S3 Console > Bucket > **Permissions** > **Bucket Policy**
2. Aşağıdaki policy'yi ekleyin (OAC ARN'ınızı değiştirin):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudFrontServicePrincipal",
            "Effect": "Allow",
            "Principal": {
                "Service": "cloudfront.amazonaws.com"
            },
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::kuafora-website/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": "arn:aws:cloudfront::ACCOUNT_ID:distribution/DISTRIBUTION_ID"
                }
            }
        }
    ]
}
```

**Not:** `ACCOUNT_ID` ve `DISTRIBUTION_ID` değerlerini CloudFront distribution detaylarından alın.

## ✅ Test Etme

### 1. Environment Variable Kontrolü

```bash
# Production server'da
echo $AWS_S3_CUSTOM_DOMAIN
# Çıktı: d1234567890abc.cloudfront.net veya cdn.kuafora.com
```

### 2. Django Static URL Kontrolü

```python
# Django shell'de
from django.conf import settings
print(settings.STATIC_URL)
# Çıktı: https://d1234567890abc.cloudfront.net/static/
```

### 3. Browser'da Test

1. Website'i açın
2. Developer Tools > Network sekmesi
3. Bir görsel yüklenirken:
   - **Request URL**: `https://d1234567890abc.cloudfront.net/static/img/screens/home-screen.png`
   - **Response Headers**: `x-cache: Hit from cloudfront` (cache'den geldiğinde)
   - **Status**: `200 OK`

### 4. CloudFront Cache Test

```bash
# CloudFront distribution'dan direkt test
curl -I https://d1234567890abc.cloudfront.net/static/img/screens/home-screen.png

# Response headers'da şunları görmelisiniz:
# x-cache: Hit from cloudfront (cache'den)
# x-cache: Miss from cloudfront (S3'ten yeni yüklendi)
```

## 🔄 Cache Invalidation (Görsel Güncelleme)

Görselleri güncellediğinizde CloudFront cache'ini temizlemeniz gerekebilir:

### AWS Console'dan:

1. CloudFront > Distributions > Distribution seçin
2. **Invalidations** tab'ına gidin
3. **Create Invalidation** butonuna tıklayın
4. **Object Paths** alanına:
   - Tek görsel: `/static/img/screens/home-screen.png`
   - Tüm görseller: `/static/img/screens/*`
   - Tüm static files: `/static/*`
5. **Create Invalidation** butonuna tıklayın

### AWS CLI ile:

```bash
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/static/img/screens/*"
```

## 📊 Monitoring ve Optimizasyon

### CloudWatch Metrikleri

CloudFront distribution'ınızın performansını izleyin:
- **Requests**: Toplam istek sayısı
- **Bytes Downloaded**: İndirilen veri miktarı
- **4xx/5xx Error Rate**: Hata oranları
- **Cache Hit Rate**: Cache başarı oranı (yüksek olmalı)

### Optimizasyon İpuçları

1. **Cache Headers**: Django'da `AWS_S3_OBJECT_PARAMETERS` ile cache headers ayarlayın
2. **Image Optimization**: Görselleri optimize edin (TinyPNG, Squoosh)
3. **Lazy Loading**: Template'lerde `loading="lazy"` kullanın
4. **WebP Format**: Modern tarayıcılar için WebP formatı kullanın

## 🐛 Sorun Giderme

### Sorun 1: Görseller yüklenmiyor (403 Forbidden)

**Çözüm:**
- S3 bucket policy'yi kontrol edin
- Origin Access Control ayarlarını kontrol edin
- CloudFront distribution'ın S3 bucket'a erişim yetkisi olduğundan emin olun

### Sorun 2: Eski görseller gösteriliyor

**Çözüm:**
- CloudFront cache invalidation yapın
- Cache TTL ayarlarını kontrol edin
- Browser cache'ini temizleyin

### Sorun 3: CloudFront domain çalışmıyor

**Çözüm:**
- Distribution'ın "Deployed" durumunda olduğundan emin olun
- DNS propagation için birkaç dakika bekleyin
- Environment variable'ın doğru olduğundan emin olun

## 📝 Özet

CloudFront kurulumu için:

1. ✅ CloudFront distribution oluştur (S3 bucket'ı origin olarak)
2. ✅ S3 bucket policy'yi güncelle (OAC için)
3. ✅ `AWS_S3_CUSTOM_DOMAIN` environment variable'ını ayarla
4. ✅ Django uygulamasını yeniden başlat
5. ✅ Test et ve cache invalidation yap (gerekirse)

Görseller artık CloudFront CDN üzerinden yüklenecek! 🚀
