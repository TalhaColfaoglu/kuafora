Dev/Prod env yönetimi (Sunucu)

ÖNEMLİ: env/.env dosyası KULLANILMAZ. Backend container'ları şu dosyaları okur:
  - backend (prod): ./env/backend.env
  - backend_dev:     ./env/backend.dev.env

- Prod env dosyaları:
  - ./env/db.env
  - ./env/backend.env
  - ./env/website.env

- Dev env dosyaları (repo'ya girmez, sunucuda oluşturulur):
  - ./env/db.dev.env        (örnek: ./env/db.dev.env.example)
  - ./env/backend.dev.env  (örnek: ./env/backend.dev.env.example)  <-- Gmail API buraya yazılır

Notlar:
- Dev ve prod DB mutlaka ayrı olmalı.
- backend_dev servisinde POSTGRES_HOST=db_dev olmalı.
- api-dev.kuafora.com için nginx vhost: ./nginx/conf.d/api-dev.conf
- Gmail API için: GMAIL_API_* değişkenlerini env/backend.dev.env içine ekleyin (bu dosya backend_dev tarafından okunur).

--- PROD KONTROL LİSTESİ (prod görseller yüklenmiyor / prod db kullanılmıyor ise) ---

1) Prod DB kullanılıyor mu?
   - env/backend.env içinde POSTGRES_HOST=db olmalı (db_dev DEĞİL).
   - POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD env/db.env'deki BACKEND_DB, BACKEND_USER, BACKEND_PASSWORD ile aynı olmalı.
   - Kontrol: backend container'da env | grep POSTGRES

2) Görseller yükleniyor mu?
   - env/backend.env içinde PUBLIC_API_ORIGIN=https://api.kuafora.com olmalı (sonunda / yok).
   - S3 kullanıyorsanız: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY ve bucket ayarları dolu olmalı.
   - S3 kullanmıyorsanız: Medya dosyaları backend_media volume'da; Nginx /media/ isteklerini backend'e yönlendiriyor olmalı.
   - Kontrol: API'den dönen campaign/shop image URL'leri https://api.kuafora.com/... ile başlamalı (172.x, backend:8000 olmamalı).


