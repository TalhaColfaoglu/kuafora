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


