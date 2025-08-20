# Kuafora.com Deployment Guide

Bu rehber, Kuafora.com'u AWS Ubuntu server'ına Docker, Nginx ve Gunicorn kullanarak deploy etmek için hazırlanmıştır.

## 🚀 Hızlı Başlangıç

### 1. Server Hazırlığı

```bash
# Ubuntu 22.04 LTS server'ınızda
sudo apt update && sudo apt upgrade -y
```

### 2. Projeyi Server'a Yükleme

```bash
# Projeyi klonlayın
git clone https://github.com/yourusername/kuafora-website.git
cd kuafora-website

# Deploy script'ini çalıştırın
./deploy.sh
```

### 3. Environment Değişkenlerini Ayarlama

```bash
# Production environment'ı düzenleyin
nano .env.prod

# Database environment'ı düzenleyin
nano .env.prod.db
```

## 📋 Detaylı Kurulum

### Gereksinimler

- Ubuntu 22.04 LTS
- 2GB+ RAM
- 20GB+ Disk alanı
- Root erişimi
- Domain name (kuafora.com)

### Adım Adım Kurulum

#### 1. Environment Dosyalarını Hazırlayın

```bash
# .env.prod dosyasını oluşturun
cp env.prod.example .env.prod

# Önemli değişkenleri güncelleyin:
# - SECRET_KEY: Güçlü bir secret key
# - ALLOWED_HOSTS: kuafora.com,www.kuafora.com,your-server-ip
# - DATABASE_URL: PostgreSQL bağlantı string'i
```

#### 2. SSL Sertifikası Kurulumu

```bash
# Let's Encrypt ile SSL sertifikası
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@kuafora.com \
    --agree-tos \
    --no-eff-email \
    -d kuafora.com \
    -d www.kuafora.com
```

#### 3. Servisleri Başlatma

```bash
# Docker servisleri başlat
docker-compose -f docker-compose.prod.yml up -d

# Database migration
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# Static files
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Superuser oluştur
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

## 🔧 Yönetim Komutları

### Servis Yönetimi

```bash
# Servisleri başlat
docker-compose -f docker-compose.prod.yml up -d

# Servisleri durdur
docker-compose -f docker-compose.prod.yml down

# Servisleri yeniden başlat
docker-compose -f docker-compose.prod.yml restart

# Logları görüntüle
docker-compose -f docker-compose.prod.yml logs -f
```

### Güncelleme

```bash
# Otomatik güncelleme
./update.sh

# Manuel güncelleme
git pull origin main
docker-compose -f docker-compose.prod.yml up -d --build
```

### Backup

```bash
# Manuel backup
./backup.sh

# Backup'ı restore etme
gunzip < /opt/backups/kuafora_backup_YYYYMMDD_HHMMSS.sql.gz | \
docker-compose -f docker-compose.prod.yml exec -T db psql -U kuafora_user -d kuafora_db
```

## 🛡️ Güvenlik

### Firewall Ayarları

```bash
# UFW firewall
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### SSL Yenileme

SSL sertifikaları otomatik olarak yenilenir. Manuel yenilemek için:

```bash
docker-compose -f docker-compose.prod.yml run --rm certbot renew
docker-compose -f docker-compose.prod.yml restart nginx
```

## 📊 Monitoring

### Health Check

```bash
# Servis durumu kontrol
curl -f https://kuafora.com/health/

# Detaylı sistem durumu
docker-compose -f docker-compose.prod.yml ps
```

### Loglar

```bash
# Tüm servis logları
docker-compose -f docker-compose.prod.yml logs -f

# Sadece web servis logları
docker-compose -f docker-compose.prod.yml logs -f web

# Nginx logları
docker-compose -f docker-compose.prod.yml logs -f nginx
```

## 🔧 Sorun Giderme

### Yaygın Sorunlar

#### 1. SSL Sertifikası Hatası

```bash
# Nginx konfigürasyonunu kontrol et
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# SSL sertifikalarını yenile
docker-compose -f docker-compose.prod.yml run --rm certbot renew
```

#### 2. Database Bağlantı Hatası

```bash
# Database servisini kontrol et
docker-compose -f docker-compose.prod.yml logs db

# Database'e bağlan
docker-compose -f docker-compose.prod.yml exec db psql -U kuafora_user -d kuafora_db
```

#### 3. Static Files Yüklenmeme

```bash
# Static files'ı yeniden topla
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Nginx'i yeniden başlat
docker-compose -f docker-compose.prod.yml restart nginx
```

## 🌐 Domain Ayarları

### DNS Kayıtları

Kuafora.com domain'i için şu DNS kayıtlarını ekleyin:

```
A     kuafora.com     YOUR_SERVER_IP
A     www.kuafora.com YOUR_SERVER_IP
```

### Cloudflare (Opsiyonel)

Cloudflare kullanıyorsanız:

1. SSL/TLS modu: "Full (strict)"
2. Always Use HTTPS: Aktif
3. HSTS: Aktif
4. Minimum TLS Version: 1.2

## 📈 Performans Optimizasyonu

### 1. Database Optimizasyonu

```bash
# Database index'leri kontrol et
docker-compose -f docker-compose.prod.yml exec web python manage.py dbshell
```

### 2. Cache Ayarları

Redis cache varsayılan olarak aktif. Cache'i temizlemek için:

```bash
docker-compose -f docker-compose.prod.yml exec redis redis-cli FLUSHALL
```

### 3. Static Files CDN

Production'da static files'ları CDN'e yüklemek için `settings.py`'da:

```python
# AWS S3 veya Cloudflare için
STATICFILES_STORAGE = 'your_cdn_storage_backend'
```

## 🔄 Otomatik Deployments

GitHub Actions ile otomatik deployment için `.github/workflows/deploy.yml` oluşturun:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.KEY }}
          script: |
            cd /opt/kuafora
            ./update.sh
```

## 📞 Destek

Sorun yaşarsanız:

1. Logları kontrol edin: `docker-compose logs -f`
2. Health check yapın: `curl https://kuafora.com/health/`
3. GitHub Issues'da yeni issue açın

## 📝 Notlar

- Backup'lar otomatik olarak her gece 02:00'da alınır
- SSL sertifikaları otomatik olarak yenilenir
- Log rotation otomatik olarak yapılır
- Health check endpoint: `/health/`

---

**Önemli:** Production'da mutlaka:
- `SECRET_KEY`'i değiştirin
- Database şifrelerini güçlü yapın
- Admin şifresini değiştirin
- Firewall ayarlarını yapın