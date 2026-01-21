# Log Rotation Kurulum Rehberi

Bu rehber, Docker container log rotation ve Django application log rotation kurulumunu açıklar.

## 🎯 Neden Log Rotation?

- **Disk alanı koruması**: Log dosyaları disk'i doldurmasın
- **Performans**: Büyük log dosyaları okuma/yazmayı yavaşlatır
- **Maliyet**: Disk alanı maliyetlidir
- **Yönetim**: Eski loglar otomatik temizlenir

## 📋 Yapılacaklar

### 1. Docker Daemon Log Rotation (ÖNEMLİ - Server'da yapılacak)

Docker container'larının log dosyalarını otomatik temizler.

#### Adım 1: Docker daemon config dosyasını oluştur/düzenle

```bash
# Server'da SSH ile bağlan
ssh ubuntu@3.122.14.242

# Docker daemon config dosyasını kontrol et
sudo cat /etc/docker/daemon.json

# Eğer dosya yoksa veya içeriği farklıysa, düzenle:
sudo nano /etc/docker/daemon.json
```

#### Adım 2: İçeriği ekle/düzenle

**Eğer dosya boşsa veya yoksa**, şunu ekle:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "compress": "true"
  }
}
```

**Eğer dosyada zaten içerik varsa** (örneğin registry ayarları), sadece `log-opts` kısmını ekle:

```json
{
  "registry-mirrors": ["..."],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "compress": "true"
  }
}
```

**Açıklama:**
- `max-size`: Her log dosyası maksimum 10MB
- `max-file`: Maksimum 3 dosya tutulur (toplam ~30MB)
- `compress`: Eski loglar otomatik sıkıştırılır

#### Adım 3: Docker'ı restart et

```bash
# Docker'ı restart et
sudo systemctl restart docker

# Docker'ın çalıştığını kontrol et
sudo systemctl status docker
```

#### Adım 4: Container'ları restart et

```bash
cd ~/kuafora
docker compose restart
```

#### Adım 5: Log rotation'ın çalıştığını kontrol et

```bash
# Log dosyalarının boyutunu kontrol et
sudo du -sh /var/lib/docker/containers/*/*.log

# Toplam log boyutu
sudo du -sh /var/lib/docker/containers/

# En büyük log dosyaları (ilk 10)
sudo find /var/lib/docker/containers/ -name "*.log" -exec ls -lh {} \; | awk '{print $5, $9}' | sort -hr | head -10
```

### 2. Django Application Log Rotation (Otomatik - Kod içinde)

Django logging config'i zaten `settings.py`'a eklendi. Log dosyaları `/app/logs/` dizininde tutulacak.

#### Log Dosyaları:
- `/app/logs/django.log` - Genel loglar (10MB, 5 backup)
- `/app/logs/django_errors.log` - Sadece ERROR seviyesi (10MB, 5 backup)

#### Kontrol:

```bash
# Container içinde log dizinini kontrol et
docker compose exec backend_dev ls -lh /app/logs/

# Log dosyalarının boyutunu kontrol et
docker compose exec backend_dev du -sh /app/logs/*
```

## 🔍 Log Rotation Nasıl Çalışır?

### Docker Log Rotation:
1. Log dosyası 10MB'a ulaştığında otomatik rotate edilir
2. Eski dosya `.log.1`, `.log.2` gibi isimlerle saklanır
3. 3 dosyadan fazlası otomatik silinir
4. Eski dosyalar sıkıştırılır (`.log.1.gz`)

### Django Log Rotation:
1. Log dosyası 10MB'a ulaştığında otomatik rotate edilir
2. Eski dosya `.log.1`, `.log.2` gibi isimlerle saklanır
3. 5 dosyadan fazlası otomatik silinir
4. Toplam maksimum ~50MB log tutulur

## 📊 Log Boyutları

### Önerilen Ayarlar:

**Küçük/Orta Projeler:**
- Docker: 10MB x 3 dosya = ~30MB
- Django: 10MB x 5 dosya = ~50MB
- **Toplam: ~80MB**

**Büyük Projeler:**
- Docker: 50MB x 5 dosya = ~250MB
- Django: 50MB x 10 dosya = ~500MB
- **Toplam: ~750MB**

## ✅ Test ve Doğrulama

### Docker Log Rotation Test:

```bash
# Mevcut log boyutlarını kontrol et
sudo du -sh /var/lib/docker/containers/*/*.log

# Log rotation'ın çalıştığını görmek için bir süre bekleyin
# Veya manuel olarak log oluşturun (test için)
docker compose logs backend_dev | head -100 > /tmp/test.log
```

### Django Log Rotation Test:

```bash
# Log dosyalarını kontrol et
docker compose exec backend_dev ls -lh /app/logs/

# Log içeriğini görüntüle
docker compose exec backend_dev tail -f /app/logs/django.log
```

## 🚨 Sorun Giderme

### Docker log rotation çalışmıyor:

1. **Config dosyasını kontrol et:**
   ```bash
   sudo cat /etc/docker/daemon.json
   ```

2. **Docker'ı restart et:**
   ```bash
   sudo systemctl restart docker
   ```

3. **Container'ları yeniden oluştur:**
   ```bash
   cd ~/kuafora
   docker compose down
   docker compose up -d
   ```

### Django log rotation çalışmıyor:

1. **Log dizininin var olduğunu kontrol et:**
   ```bash
   docker compose exec backend_dev ls -ld /app/logs
   ```

2. **Dizin yoksa oluştur:**
   ```bash
   docker compose exec backend_dev mkdir -p /app/logs
   docker compose exec backend_dev chmod 755 /app/logs
   ```

3. **Container'ı restart et:**
   ```bash
   docker compose restart backend_dev
   ```

## 📝 Notlar

- Log rotation **otomatik** çalışır, manuel müdahale gerekmez
- Eski loglar **sıkıştırılır**, disk alanı tasarrufu sağlar
- Log dosyaları **güvenli** şekilde saklanır, hassas bilgiler içermez (sanitize edilmiş)
- Production'da log seviyesi **INFO** olarak ayarlanmıştır (DEBUG değil)

## 🔗 İlgili Dosyalar

- `config/settings.py` - Django logging config
- `Dockerfile.prod` - Log dizini oluşturma
- `docker-daemon.json.example` - Docker daemon config örneği

