# Prod backend launch – SSH komutları

Sunucuya SSH ile bağlandıktan sonra aşağıdaki komutları kullanın.  
`docker-compose.yml` dosyası **kuafora/** dizininde (repo kökündeki `kuafora` klasörü).

---

## 1. Proje dizinine geç

```bash
cd ~/backend-frontend/kuafora
```

(Sunucudaki gerçek path farklıysa, `docker-compose.yml` olan dizine gidin.)

---

## 2. Sadece prod backend’i ilk kez / yeniden başlat

Prod API (api.kuafora.com) için gerekli servisler: **db**, **redis**, **backend**, **nginx**.

```bash
docker compose up -d db redis backend nginx
```

Tüm prod + dev + website + cron + worker da açılsın isterseniz:

```bash
docker compose up -d
```

---

## 3. Kod güncelledikten sonra backend’i yeniden build et ve çalıştır

```bash
cd ~/backend-frontend/kuafora

docker compose build backend --no-cache
docker compose up -d backend
```

Migrate ve collectstatic **entrypoint** içinde çalışıyor; container ayağa kalkınca otomatik yapılır.

---

## 4. Sadece backend container’ını yeniden başlat (build yok)

```bash
docker compose restart backend
```

---

## 5. Logları izle

```bash
# Sadece prod backend
docker compose logs -f backend

# Son 200 satır
docker compose logs -f --tail=200 backend
```

---

## 6. Container durumunu kontrol et

```bash
docker compose ps
```

---

## 7. (İsteğe bağlı) Migrate / collectstatic’i elle çalıştır

```bash
docker compose exec backend python manage.py migrate --noinput
docker compose exec backend python manage.py collectstatic --noinput --clear
docker compose restart backend
```

---

## 8. Prod backend’e bağlı diğer servisler

- **cron** – zamanlanmış işler  
- **notify_worker** – bildirim işçisi  

Bunları da açmak için:

```bash
docker compose up -d db redis backend cron notify_worker nginx
```

---

## Özet – tek seferde prod backend launch

```bash
cd ~/backend-frontend/kuafora
docker compose up -d db redis backend nginx
docker compose ps
docker compose logs -f --tail=50 backend
```

(Ctrl+C ile logdan çıkarsınız; container çalışmaya devam eder.)
