# Migration Talimatları

## 1. Core App Migration (AppVersion modeli için)

```bash
cd /Users/talhacolfaoglu/Desktop/backend-frontend/kuafora
docker compose exec backend python manage.py makemigrations core
docker compose exec backend python manage.py migrate core
```

## 2. Barbers App Migration (0033 - Düzeltilmiş)

Migration dosyası zaten oluşturuldu ve `google_maps_link` ekleme işlemi çıkarıldı (zaten var).

```bash
docker compose exec backend python manage.py migrate barbers
```

Eğer hala hata verirse:

```bash
# Migration'ı fake et (zaten uygulanmış gibi işaretle)
docker compose exec backend python manage.py migrate barbers 0033 --fake

# Sonra diğer migration'ları çalıştır
docker compose exec backend python manage.py migrate
```

## 3. Tüm Migration'ları Çalıştırma

```bash
docker compose exec backend python manage.py migrate
```

## Sorun Giderme

### Eğer `google_maps_link` hatası devam ederse:

1. Migration dosyasını kontrol edin: `app/barbers/migrations/0033_*.py`
2. `google_maps_link` ekleme işlemi olmamalı
3. Eğer varsa, migration dosyasından çıkarın

### Eğer index hatası alırsanız:

Index'ler zaten var olabilir. Bu durumda migration'ı fake edin:

```bash
docker compose exec backend python manage.py migrate barbers 0033 --fake
```
