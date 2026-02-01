# SSH – Backend Dev (Docker) Komutları

Sunucuya bağlandıktan sonra proje köküne gidin (docker-compose.yml burada):
```bash
cd ~/kuafora
# veya projenin bulunduğu path:
# cd /path/to/kuafora
```

---

## Genel

| Açıklama | Komut |
|----------|--------|
| **Sadece backend_dev + bağımlılıkları çalıştır** | `docker compose up -d db_dev redis backend_dev` |
| **Tüm stack’i çalıştır** | `docker compose up -d` |
| **backend_dev’i durdur** | `docker compose stop backend_dev` |
| **backend_dev’i kaldır (container silinir)** | `docker compose rm -f backend_dev` |

---

## Build & Güncelleme

| Açıklama | Komut |
|----------|--------|
| **backend_dev’i yeniden build et** | `docker compose build backend_dev` |
| **Build edip yeniden başlat (güncelleme)** | `docker compose build backend_dev && docker compose up -d backend_dev` |
| **Cache kullanmadan temiz build** | `docker compose build --no-cache backend_dev` |

---

## Loglar & Shell

| Açıklama | Komut |
|----------|--------|
| **backend_dev loglarını izle** | `docker compose logs -f backend_dev` |
| **Son 200 satır log** | `docker compose logs --tail 200 backend_dev` |
| **backend_dev container’a shell** | `docker compose exec backend_dev sh` |
| **Django manage.py (container içinde)** | `docker compose exec backend_dev python manage.py <komut>` |
| **Örnek: migrate** | `docker compose exec backend_dev python manage.py migrate` |
| **Örnek: createsuperuser** | `docker compose exec backend_dev python manage.py createsuperuser` |
| **Örnek: collectstatic** | `docker compose exec backend_dev python manage.py collectstatic --noinput` |

---

## Durum Kontrolü

| Açıklama | Komut |
|----------|--------|
| **backend_dev durumu** | `docker compose ps backend_dev` |
| **Tüm servisler** | `docker compose ps` |
| **backend_dev + db_dev + redis sağlık** | `docker compose ps db_dev redis backend_dev` |

---

## Tek Satırda Güncelleme (kod çekip yeniden başlatma)

```bash
cd ~/kuafora && git pull && docker compose build backend_dev && docker compose up -d backend_dev
```

---

## Notlar

- **backend_dev** servisi `db_dev` ve `redis`’e bağlı; önce onların ayakta olduğundan emin olun.
- Env dosyası: `./env/backend.dev.env` (sunucuda bu path’te olmalı).
- Container adı: `kuafora_backend_dev`.
- Port: 8000 (nginx üzerinden api-dev.kuafora.com’a yönlendirilir).
