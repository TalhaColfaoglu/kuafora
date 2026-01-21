# Monitoring Kurulum Rehberi

Bu rehber, Kuafora uygulamasının monitoring (izleme) sistemini açıklar.

## 🎯 Monitoring Nedir?

Monitoring, sunucu ve uygulamanın sağlığını sürekli izleme ve sorunları erken tespit etme sistemidir.

### Ne İzlenir?

1. **Sunucu Sağlığı**
   - CPU kullanımı
   - RAM kullanımı
   - Disk alanı
   - Ağ trafiği

2. **Uygulama Sağlığı**
   - Database bağlantı durumu
   - Cache bağlantı durumu
   - API yanıt süreleri
   - Hata oranları

3. **Güvenlik**
   - Başarısız login denemeleri
   - Şüpheli aktiviteler
   - Rate limit aşımları

## 📋 Kurulum

### 1. Paket Kurulumu

Monitoring için `psutil` paketi gerekli. Zaten `requirements.txt`'e eklendi:

```bash
# Server'da
cd ~/kuafora/kuafora-mobile-app-backend
pip install psutil==5.9.8
# Veya Docker container içinde
docker compose exec backend_dev pip install psutil==5.9.8
```

### 2. API Endpoints

Monitoring sistemi şu endpoint'leri sağlar:

#### `/health/` - Basit Health Check
Load balancer'lar için basit health check:
```bash
curl http://localhost:8000/health/
# Response: {"status": "ok"}
```

#### `/api/health/` - Detaylı Health Check
Kapsamlı sistem sağlık kontrolü:
```bash
curl http://localhost:8000/api/health/
# Response:
# {
#   "status": "healthy",
#   "timestamp": "2024-01-21T17:30:00",
#   "database": {"status": "healthy"},
#   "cache": {"status": "healthy"},
#   "disk": {"status": "healthy", "percent_used": 45.2, ...}
# }
```

#### `/api/metrics/` - Sistem Metrikleri
CPU, RAM, Disk ve uygulama metrikleri:
```bash
curl http://localhost:8000/api/metrics/
# Response:
# {
#   "system": {
#     "cpu": {"percent": 25.5, "count": 2},
#     "memory": {"total_gb": 4.0, "used_gb": 2.1, "percent": 52.5},
#     "disk": {...}
#   },
#   "application": {
#     "users": {"total": 150, "active": 120},
#     "barbershops": {"total": 50, "approved": 45}
#   }
# }
```

## 🔔 Otomatik Uyarılar

### Management Command

Health check'i manuel çalıştırabilirsiniz:

```bash
# Sadece kontrol et (email gönderme)
python manage.py check_health

# Kontrol et ve email gönder
python manage.py check_health --send-alerts --alert-email colfaoglutalha@gmail.com
```

### Cron Job Kurulumu

Otomatik uyarılar için cron job ekleyin:

```bash
# Server'da
crontab -e

# Her 15 dakikada bir kontrol et ve email gönder
*/15 * * * * cd /home/ubuntu/kuafora/kuafora-mobile-app-backend && docker compose exec -T backend_dev python manage.py check_health --send-alerts --alert-email colfaoglutalha@gmail.com

# Veya script kullanarak
*/15 * * * * /home/ubuntu/kuafora/kuafora-mobile-app-backend/monitoring_check.sh
```

**Not:** Script'i çalıştırılabilir yapın:
```bash
chmod +x monitoring_check.sh
```

## 📊 Uyarı Koşulları

Sistem şu durumlarda email uyarısı gönderir:

1. **Critical**: Disk kullanımı %90'ın üzerinde
2. **Warning**: Disk kullanımı %80'in üzerinde
3. **Unhealthy**: Database bağlantısı başarısız
4. **Unhealthy**: Genel sistem sağlığı "unhealthy"

## 🔍 Monitoring Kontrolü

### Health Check Test

```bash
# Basit health check
curl http://localhost:8000/health/

# Detaylı health check
curl http://localhost:8000/api/health/

# Metrikler
curl http://localhost:8000/api/metrics/
```

### Management Command Test

```bash
# Container içinde
docker compose exec backend_dev python manage.py check_health

# Email göndermeden test
docker compose exec backend_dev python manage.py check_health --send-alerts --alert-email colfaoglutalha@gmail.com
```

## 📧 Email Ayarları

Email uyarıları için `settings.py`'daki email ayarlarının doğru yapılandırıldığından emin olun:

```python
EMAIL_HOST = "email-smtp.eu-central-1.amazonaws.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "your-ses-smtp-username"
EMAIL_HOST_PASSWORD = "your-ses-smtp-password"
DEFAULT_FROM_EMAIL = "Kuafora <noreply@kuafora.com>"
```

## 🚨 Sorun Giderme

### Health Check Başarısız

1. **Database bağlantısı kontrolü:**
   ```bash
   docker compose exec backend_dev python manage.py dbshell
   ```

2. **Cache bağlantısı kontrolü:**
   ```bash
   docker compose exec backend_dev python manage.py shell
   >>> from django.core.cache import cache
   >>> cache.set('test', 'ok', 10)
   >>> cache.get('test')
   ```

3. **Disk alanı kontrolü:**
   ```bash
   df -h
   ```

### Metrics Endpoint Hata Veriyor

1. **psutil kurulu mu kontrol et:**
   ```bash
   docker compose exec backend_dev pip list | grep psutil
   ```

2. **Gerekirse yeniden kur:**
   ```bash
   docker compose exec backend_dev pip install psutil==5.9.8
   ```

### Email Gönderilmiyor

1. **Email ayarlarını kontrol et:**
   ```bash
   docker compose exec backend_dev python manage.py shell
   >>> from django.conf import settings
   >>> print(settings.EMAIL_HOST)
   >>> print(settings.DEFAULT_FROM_EMAIL)
   ```

2. **Test email gönder:**
   ```bash
   docker compose exec backend_dev python manage.py shell
   >>> from django.core.mail import send_mail
   >>> send_mail('Test', 'Test message', 'noreply@kuafora.com', ['colfaoglutalha@gmail.com'])
   ```

## 📝 Notlar

- Health check endpoint'leri **public** (authentication gerektirmez)
- Metrics endpoint'i de **public** (sensitive bilgi içermez)
- Email uyarıları sadece kritik durumlarda gönderilir
- Cron job her 15 dakikada bir çalışır (ayarlanabilir)

## 🔗 İlgili Dosyalar

- `app/core/monitoring.py` - Monitoring utilities
- `app/core/views.py` - Health check ve metrics endpoints
- `app/core/management/commands/check_health.py` - Health check command
- `monitoring_check.sh` - Cron job script
- `config/urls.py` - URL routing

## ✅ Sonraki Adımlar

1. ✅ Monitoring sistemi kuruldu
2. ⏳ Cron job ekle (server'da)
3. ⏳ Email ayarlarını doğrula
4. ⏳ Test uyarısı gönder
5. ⏳ Monitoring dashboard (opsiyonel - Grafana/Prometheus)

