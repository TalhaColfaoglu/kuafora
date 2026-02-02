#!/bin/bash
# Website 500 hatasını gidermek için düzeltilmiş şablonları sunucuya ve container'a kopyalar.
# Kullanım (yerel makinede):
#   ./deploy-fix-static-exists.sh ubuntu 3.122.14.242 ~/Downloads/makas-deneme.pem
#
# Veya sunucuda zaten SSH ile bağlıysanız, sadece aşağıdaki "Sunucuda çalıştır" bölümünü kullanın.

set -e
SSH_USER="${1:-ubuntu}"
SSH_HOST="${2:-3.122.14.242}"
SSH_KEY="${3:-$HOME/Downloads/makas-deneme.pem}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Düzeltilmiş şablonlar sunucuya kopyalanıyor..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
  "$SCRIPT_DIR/templates/marketing/home.html" \
  "$SCRIPT_DIR/templates/partner/partner_landing.html" \
  "$SSH_USER@$SSH_HOST:/tmp/"

echo "Container içine kopyalanıyor (sunucuda docker cp)..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" << 'REMOTE'
CONTAINER=$(docker ps --filter "name=kuafora_website" --format "{{.Names}}" | head -1)
if [ -z "$CONTAINER" ]; then
  CONTAINER=$(docker ps --filter "name=website" --format "{{.Names}}" | head -1)
fi
if [ -z "$CONTAINER" ]; then
  echo "HATA: kuafora_website container bulunamadı. docker ps ile kontrol edin."
  exit 1
fi
echo "Container: $CONTAINER"
docker cp /tmp/home.html "$CONTAINER:/app/templates/marketing/home.html"
docker cp /tmp/partner_landing.html "$CONTAINER:/app/templates/partner/partner_landing.html"
echo "Şablonlar güncellendi. Sayfayı yenileyin."
REMOTE

echo "Bitti."
