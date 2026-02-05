# CloudFront Hızlı Başlangıç Kılavuzu

Bu kılavuz, Kuafora website görsellerinin CloudFront CDN üzerinden yüklenmesi için hızlı kurulum adımlarını içerir.

## 🚀 Hızlı Kurulum (Script ile)

### 1. Gereksinimler

```bash
pip install boto3
```

### 2. Environment Variables Ayarlayın

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_STORAGE_BUCKET_NAME=kuafora-website
export AWS_S3_REGION_NAME=eu-central-1
```

### 3. Script'i Çalıştırın

```bash
cd kuafora/kuafora-website
python scripts/create_cloudfront_distribution.py
```

Script otomatik olarak:
- ✅ S3 bucket'ı kontrol eder
- ✅ Origin Access Control (OAC) oluşturur
- ✅ CloudFront distribution oluşturur
- ✅ S3 bucket policy'yi günceller
- ✅ CloudFront domain'ini gösterir

### 4. Environment Variable Ekleyin

Script'in gösterdiği CloudFront domain'ini production environment variable'ına ekleyin:

```bash
export AWS_S3_CUSTOM_DOMAIN=d1234567890abc.cloudfront.net
```

### 5. Django Uygulamasını Yeniden Başlatın

```bash
# Docker kullanıyorsanız
docker-compose restart website

# Veya direkt
python manage.py collectstatic --noinput
```

## ✅ Test Etme

1. Website'i açın
2. Developer Tools > Network sekmesi
3. Bir görsel yüklenirken URL'yi kontrol edin:
   - ✅ CloudFront: `https://d1234567890abc.cloudfront.net/static/img/...`
   - ❌ S3: `https://kuafora-website.s3.eu-central-1.amazonaws.com/static/img/...`

## 📋 Manuel Kurulum (AWS Console)

Script çalışmazsa AWS Console'dan manuel olarak:

1. **CloudFront Console** > **Create Distribution**
2. **Origin Domain**: `kuafora-website.s3.eu-central-1.amazonaws.com`
3. **Viewer Protocol Policy**: `Redirect HTTP to HTTPS`
4. **Allowed HTTP Methods**: `GET, HEAD, OPTIONS`
5. **Price Class**: `Use only North America and Europe`
6. **Create Distribution**
7. Distribution domain'ini `AWS_S3_CUSTOM_DOMAIN` environment variable'ına ekleyin

## 🎯 Sonuç

Görseller artık CloudFront CDN üzerinden yüklenecek:
- ⚡ Daha hızlı yükleme
- 💰 Daha düşük maliyet
- 🌍 Global performans
- 🔒 Otomatik HTTPS

## 📚 Detaylı Dokümantasyon

Daha fazla bilgi için: `CLOUDFRONT_SETUP.md`
