# Docker Server ve Website Yenileme Komutları

## 🚀 Hızlı Yenileme (Önerilen)

```bash
cd ~/kuafora

# 1. Git pull (kod güncellemelerini çek)
git pull

# 2. Backend'i yeniden build et ve başlat
docker compose build backend --no-cache
docker compose up -d backend

# 3. Website'yi yeniden build et ve başlat
docker compose build website --no-cache
docker compose up -d website

# 4. Nginx'i yeniden başlat (gerekirse)
docker compose restart nginx

# 5. Durumu kontrol et
docker compose ps
```

## 📋 Detaylı Adımlar

### 1. Sadece Backend'i Yenile

```bash
cd ~/kuafora
git pull
docker compose build backend --no-cache
docker compose up -d backend
docker compose logs -f --tail=50 backend
```

### 2. Sadece Website'yi Yenile

```bash
cd ~/kuafora
git pull
docker compose build website --no-cache
docker compose up -d website
docker compose logs -f --tail=50 website
```

### 3. Her İkisini Birlikte Yenile

```bash
cd ~/kuafora
git pull
docker compose build backend website --no-cache
docker compose up -d backend website
docker compose restart nginx
docker compose ps
```

### 4. Migrasyon ve Static Files (Gerekirse)

```bash
# Backend migrasyonları
docker compose exec backend python manage.py migrate --noinput

# Backend static files
docker compose exec backend python manage.py collectstatic --noinput

# Website migrasyonları
docker compose exec website python manage.py migrate --noinput

# Website static files
docker compose exec website python manage.py collectstatic --noinput
```

### 5. Sadece Restart (Build Olmadan)

```bash
cd ~/kuafora
docker compose restart backend website nginx
```

## 🔍 Kontrol ve Loglar

### Container Durumunu Kontrol Et

```bash
docker compose ps
```

### Logları İzle

```bash
# Backend logları
docker compose logs -f backend

# Website logları
docker compose logs -f website

# Nginx logları
docker compose logs -f nginx

# Tüm loglar
docker compose logs -f
```

### Health Check

```bash
# Backend health check
curl -f http://localhost:8000/health/ || echo "Backend sağlıksız"

# Website health check (eğer varsa)
curl -f http://localhost:8001/health/ || echo "Website sağlıksız"
```

## ⚠️ Sorun Giderme

### Container Başlamıyorsa

```bash
# Logları kontrol et
docker compose logs backend
docker compose logs website

# Container'ı yeniden oluştur
docker compose up -d --force-recreate backend website
```

### Static Files Sorunu

```bash
# Static files'ı temizle ve yeniden topla
docker compose exec backend python manage.py collectstatic --noinput --clear
docker compose exec website python manage.py collectstatic --noinput --clear
docker compose restart backend website nginx
```

## 🎯 Tek Komutla Yenileme (Tüm Sistem)

```bash
cd ~/kuafora && \
git pull && \
docker compose build backend website --no-cache && \
docker compose up -d backend website && \
docker compose restart nginx && \
docker compose ps
```
