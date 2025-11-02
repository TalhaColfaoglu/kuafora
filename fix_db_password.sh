#!/bin/bash
set -e

echo "=== Kuafora DB Şifre Senkronizasyon Script ==="

# 1) Yeni güvenli HEX şifre üret (URL-encode gerektirmez)
NEWPW=$(openssl rand -hex 32)
echo "✓ Yeni şifre üretildi"

# 2) DB container'ını ayağa kaldır
echo "✓ DB container başlatılıyor..."
docker compose up -d db
sleep 5

# 3) DB içindeki kullanıcı şifrelerini güncelle
echo "✓ DB kullanıcı şifreleri güncelleniyor..."
docker compose exec -T db bash -c "
psql -U postgres -d postgres -v ON_ERROR_STOP=1 <<SQL
ALTER USER kuafora_backend_user WITH PASSWORD '$NEWPW';
ALTER USER kuafora_website_user WITH PASSWORD '$NEWPW';
SQL
"

# 4) Bağlantı testleri
echo "✓ Bağlantı testleri yapılıyor..."
docker compose exec -T db bash -c "PGPASSWORD='$NEWPW' psql -h 127.0.0.1 -U kuafora_backend_user -d kuafora_backend -tAc 'select 1'" > /dev/null
docker compose exec -T db bash -c "PGPASSWORD='$NEWPW' psql -h 127.0.0.1 -U kuafora_website_user -d kuafora_website -tAc 'select 1'" > /dev/null
echo "✓ DB bağlantıları başarılı"

# 5) Env dosyalarını güncelle
echo "✓ Env dosyaları güncelleniyor..."

# backend.env
cat > env/backend.env <<EOF
# Backend (kuafora-mobile-app-backend)
DEBUG=0
SECRET_KEY=osmwg))p+@+!bi&v9rj9q&t+wp+&=5=2ggw99h&lp#)st75mdg
ALLOWED_HOSTS=api.kuafora.com
CSRF_TRUSTED_ORIGINS=https://api.kuafora.com

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=kuafora_backend
POSTGRES_USER=kuafora_backend_user
POSTGRES_PASSWORD=$NEWPW
EOF

# db.env
cat > env/db.env <<EOF
# Postgres bootstrap (superuser)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$NEWPW
POSTGRES_DB=postgres

# App DBs to create via init script
BACKEND_DB=kuafora_backend
BACKEND_USER=kuafora_backend_user
BACKEND_PASSWORD=$NEWPW

WEBSITE_DB=kuafora_website
WEBSITE_USER=kuafora_website_user
WEBSITE_PASSWORD=$NEWPW
EOF

# website.env
cat > env/website.env <<EOF
# Website (kuafora-website)
DEBUG=0
SECRET_KEY=replace-with-a-strong-secret
ALLOWED_HOSTS=kuafora.com,www.kuafora.com
CSRF_TRUSTED_ORIGINS=https://kuafora.com,https://www.kuafora.com

# Database - discrete vars (fallback için)
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=kuafora_website
POSTGRES_USER=kuafora_website_user
POSTGRES_PASSWORD=$NEWPW

# DATABASE_URL (opsiyonel, yukarıdaki discrete vars yeterli)
DATABASE_URL=postgres://kuafora_website_user:$NEWPW@db:5432/kuafora_website
EOF

echo "✓ Env dosyaları güncellendi"

# 6) Container'ları yeniden oluştur
echo "✓ Backend ve Website container'ları yeniden oluşturuluyor..."
docker compose up -d --force-recreate --build backend website
sleep 10

# 7) Migrasyonları çalıştır
echo "✓ Backend migrasyonları çalıştırılıyor..."
docker compose run --rm --no-deps -T backend python manage.py migrate

echo "✓ Website migrasyonları çalıştırılıyor..."
docker compose run --rm --no-deps -T website python manage.py migrate

# 8) Health check
echo "✓ Health check yapılıyor..."
HEALTH=$(docker compose exec -T backend curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health/ || echo "000")

if [ "$HEALTH" = "200" ]; then
    echo "✅ BAŞARILI! Sistem sağlıklı çalışıyor."
    echo ""
    echo "Yeni şifre: $NEWPW"
    echo "Bu şifreyi güvenli bir yerde saklayın!"
else
    echo "⚠️  Health check başarısız (HTTP $HEALTH)"
    echo "Log kontrol edin: docker compose logs backend"
fi

echo ""
echo "=== Tamamlandı ==="

