#!/bin/bash
# Sunucuda çalıştır: chat_chatban tablosunun olduğu veritabanına expires_at kolonunu ekler.
# Kullanım: cd ~/kuafora && bash scripts/fix-chat-expires-at.sh

set -e
COMPOSE="docker compose"
DB_NAME=""
DB_USER="postgres"

# 1) Backend'den DB adı ve kullanıcı (manage.py shell ile Django yüklenir)
# Not: Backend stdout'a CloudWatch vb. yazıyor; sadece "NAME " ve "USER " satırlarını al
OUT=$($COMPOSE exec -T backend python manage.py shell -c "
from django.conf import settings
d = settings.DATABASES['default']
print('NAME', d.get('NAME', ''))
print('USER', d.get('USER', 'postgres'))
" 2>/dev/null)
if [ -n "$OUT" ]; then
  DB_NAME=$(echo "$OUT" | grep '^NAME ' | sed 's/^NAME //' | tr -d '\r\n ')
  DB_USER=$(echo "$OUT" | grep '^USER ' | sed 's/^USER //' | tr -d '\r\n ')
fi
[ -z "$DB_USER" ] && DB_USER="postgres"

# 2) Django'dan alınamadıysa: postgres ile chat_chatban olan DB'yi bul
if [ -z "$DB_NAME" ]; then
  echo "Django'dan DB alınamadı; chat_chatban olan veritabanı aranıyor..."
  DBS=$($COMPOSE exec -T db psql -U postgres -t -A -c "SELECT datname FROM pg_database WHERE datistemplate = false;" 2>/dev/null | tr -d '\r')
  for db in $DBS; do
    [ -z "$db" ] && continue
    HAS=$($COMPOSE exec -T db psql -U postgres -d "$db" -t -A -c "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='chat_chatban' LIMIT 1;" 2>/dev/null | tr -d '\r\n ')
    if [ "$HAS" = "1" ]; then
      DB_NAME="$db"
      DB_USER="postgres"
      break
    fi
  done
fi

if [ -z "$DB_NAME" ]; then
  echo "Hata: chat_chatban tablosu hiçbir veritabanında bulunamadı."
  echo "Manuel: docker compose exec db psql -U postgres -c \"\\l\" ile DB listesine bakıp, uygulama DB'sinde:"
  echo "  docker compose exec db psql -U postgres -d <DB_ADI> -c \"ALTER TABLE chat_chatban ADD COLUMN IF NOT EXISTS expires_at timestamptz NULL;\""
  exit 1
fi

echo "Veritabanı: name=$DB_NAME user=$DB_USER"
echo "Kolon ekleniyor: chat_chatban.expires_at ..."

$COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c \
  "ALTER TABLE chat_chatban ADD COLUMN IF NOT EXISTS expires_at timestamptz NULL;"

echo "Tamam. Backend'i yeniden başlat: docker compose restart backend"
