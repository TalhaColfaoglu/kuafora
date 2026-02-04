#!/bin/bash
# Sunucuda çalıştır: backend'in bağlandığı veritabanında chat_chatban.expires_at kolonunu ekler.
# Kullanım: docker compose ile aynı dizinde (örn. ~/kuafora) çalıştır:
#   bash scripts/fix-chat-expires-at.sh
# veya:
#   chmod +x scripts/fix-chat-expires-at.sh && ./scripts/fix-chat-expires-at.sh

set -e
COMPOSE="docker compose"

# Backend container'dan Django DB ayarlarını al
DB_NAME=$($COMPOSE exec -T backend python -c "
from django.conf import settings
print(settings.DATABASES['default'].get('NAME', ''))
" 2>/dev/null | tr -d '\r\n')

DB_USER=$($COMPOSE exec -T backend python -c "
from django.conf import settings
print(settings.DATABASES['default'].get('USER', 'postgres'))
" 2>/dev/null | tr -d '\r\n')

if [ -z "$DB_NAME" ]; then
  echo "Hata: Backend'den DB adı alınamadı. backend container çalışıyor mu?"
  exit 1
fi

echo "Backend DB: name=$DB_NAME user=$DB_USER"
echo "Kolon ekleniyor: chat_chatban.expires_at ..."

$COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c \
  "ALTER TABLE chat_chatban ADD COLUMN IF NOT EXISTS expires_at timestamptz NULL;"

echo "Tamam. Backend'i yeniden başlat: docker compose restart backend"
