# Pagination ve Güvenlik Olaylarını İzleme

## 📄 Pagination Nedir?

Pagination, büyük veri setlerini sayfalara bölerek döndürme işlemidir.

### ❌ Önceki Durum (Sorun)

```
GET /api/barbershops/
→ Tüm kuaförler (1000+ kayıt) tek seferde dönüyor
→ Yavaş yanıt süresi (5-10 saniye)
→ Büyük veri transferi (5-10 MB)
→ Yüksek sunucu yükü
→ Database timeout riski
```

### ✅ Yeni Durum (Çözüm)

```
GET /api/barbershops/?page=1&page_size=20
→ Sadece ilk 20 kuaför dönüyor
→ Hızlı yanıt süresi (<1 saniye)
→ Küçük veri transferi (50-100 KB)
→ Düşük sunucu yükü
→ Database performansı korunur
```

## 🔧 Pagination Kullanımı

### Backend (Otomatik)

Pagination artık **otomatik** olarak tüm ViewSet'lerde aktif:

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,  # Varsayılan sayfa boyutu
}
```

### API Response Formatı

**Önceki format (pagination yok):**
```json
[
  {"id": 1, "name": "Kuaför 1", ...},
  {"id": 2, "name": "Kuaför 2", ...},
  ...
  {"id": 1000, "name": "Kuaför 1000", ...}
]
```

**Yeni format (pagination ile):**
```json
{
  "count": 1000,
  "next": "http://api.kuafora.com/api/barbershops/?page=2",
  "previous": null,
  "results": [
    {"id": 1, "name": "Kuaför 1", ...},
    {"id": 2, "name": "Kuaför 2", ...},
    ...
    {"id": 20, "name": "Kuaför 20", ...}
  ]
}
```

### Query Parameters

- `page`: Sayfa numarası (varsayılan: 1)
- `page_size`: Sayfa başına kayıt sayısı (varsayılan: 20, maksimum: 100)

**Örnekler:**
```
GET /api/barbershops/?page=1&page_size=20  # İlk 20 kayıt
GET /api/barbershops/?page=2&page_size=20  # Sonraki 20 kayıt
GET /api/barbershops/?page=1&page_size=50  # İlk 50 kayıt
```

## 🔒 Güvenlik Olaylarını İzleme

### Ne İzleniyor?

1. **Başarısız Login Denemeleri**
   - Yanlış şifre
   - Olmayan kullanıcı
   - Rate limit aşımı

2. **Şüpheli Aktivite**
   - Çok fazla başarısız deneme
   - Farklı IP'lerden aynı kullanıcı
   - Anormal istek pattern'leri

3. **Rate Limit Aşımları**
   - Çok fazla istek
   - API abuse

### Nasıl İzleniyor?

**AuditLoggingMiddleware** şu olayları logluyor:

```python
# app/core/middleware.py
class AuditLoggingMiddleware:
    SENSITIVE_PATHS = [
        '/api/auth/login/',
        '/api/auth/register/',
        '/api/auth/change-password/'
    ]
```

**Log Formatı:**
```
[AUDIT] Failed attempt: {
    'path': '/api/auth/login/',
    'method': 'POST',
    'status': 401,
    'duration': '0.123s',
    'ip': '192.168.1.100',
    'user_agent': 'Mozilla/5.0...'
}
```

### Log Dosyaları

Güvenlik olayları şu dosyalara loglanıyor:

- `/app/logs/django.log` - Genel loglar
- `/app/logs/django_errors.log` - Sadece hatalar

**Log Kontrolü:**
```bash
# Başarısız login denemelerini görüntüle
docker compose exec backend_dev grep "AUDIT.*Failed" /app/logs/django.log

# Son 50 güvenlik olayını görüntüle
docker compose exec backend_dev tail -50 /app/logs/django.log | grep AUDIT
```

## 📊 Pagination Avantajları

1. **Performans**
   - Daha hızlı yanıt süreleri
   - Düşük database yükü
   - Daha az bellek kullanımı

2. **Kullanıcı Deneyimi**
   - Daha hızlı yükleme
   - Daha az veri transferi
   - Daha iyi mobil performans

3. **Güvenlik**
   - DDoS koruması
   - Database timeout önleme
   - Sunucu kaynak koruması

## 🚨 Güvenlik İzleme Avantajları

1. **Erken Tespit**
   - Saldırıları erken fark etme
   - Şüpheli aktiviteyi yakalama
   - Rate limit aşımlarını izleme

2. **Forensics**
   - Saldırı sonrası analiz
   - Kullanıcı aktivite takibi
   - Güvenlik olaylarını kanıtlama

3. **Compliance**
   - KVKK uyumluluğu
   - Güvenlik standartları
   - Audit trail

## 🔍 Monitoring

### Pagination Metrikleri

```bash
# API yanıt sürelerini kontrol et
curl -w "@-" -o /dev/null -s "https://api.kuafora.com/api/barbershops/?page=1&page_size=20"

# Sayfa boyutlarını kontrol et
curl "https://api.kuafora.com/api/barbershops/?page=1&page_size=20" | jq '.count'
```

### Güvenlik Olayları İzleme

```bash
# Son 1 saatteki başarısız login denemeleri
docker compose exec backend_dev grep "AUDIT.*Failed" /app/logs/django.log | tail -20

# Belirli bir IP'den gelen istekler
docker compose exec backend_dev grep "192.168.1.100" /app/logs/django.log
```

## ✅ Sonuç

- ✅ Pagination aktif (tüm ViewSet'lerde)
- ✅ Güvenlik olayları loglanıyor
- ✅ Performans iyileştirildi
- ✅ Güvenlik izleme aktif

## 📝 Notlar

- Pagination varsayılan olarak **20 kayıt** döndürür
- Maksimum `page_size` **100** olarak sınırlandırılmıştır
- Frontend'de pagination desteği eklenmelidir (infinite scroll veya sayfa numaraları)
- Güvenlik logları **7 gün** saklanır (log rotation ile)

