#!/bin/bash
# Docker Container içinde çalışacak backup script'i
# Bu script backup container'ı içinde çalışır

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Backup dizinleri
BACKUP_BASE_DIR="/backups/kuafora"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/$DATE"
LOG_FILE="$BACKUP_BASE_DIR/backup.log"

# Log fonksiyonu
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

mkdir -p "$BACKUP_DIR"

log "=== Backup başlatıldı (Docker Container) ==="

# PostgreSQL şifresi
export PGPASSWORD="${BACKEND_PASSWORD:-lNkMJJGsdbbe8CZ3hu0DuHpFyRoKAeWG0kkDiNNb20}"

# 1. PROD Veritabanı Backup
log "PROD veritabanı yedekleniyor..."
if pg_dump -h db -U kuafora_backend_user -d kuafora_backend > "$BACKUP_DIR/db_prod_$DATE.sql" 2>>"$LOG_FILE"; then
    gzip "$BACKUP_DIR/db_prod_$DATE.sql"
    DB_SIZE=$(du -h "$BACKUP_DIR/db_prod_$DATE.sql.gz" | cut -f1)
    log_success "PROD veritabanı yedeklendi: $DB_SIZE"
else
    log_error "PROD veritabanı yedekleme başarısız!"
fi

# 2. DEV Veritabanı Backup
log "DEV veritabanı yedekleniyor..."
if pg_dump -h db_dev -U kuafora_backend_user -d kuafora_backend > "$BACKUP_DIR/db_dev_$DATE.sql" 2>>"$LOG_FILE"; then
    gzip "$BACKUP_DIR/db_dev_$DATE.sql"
    DB_SIZE=$(du -h "$BACKUP_DIR/db_dev_$DATE.sql.gz" | cut -f1)
    log_success "DEV veritabanı yedeklendi: $DB_SIZE"
else
    log_warning "DEV veritabanı yedekleme başarısız (dev ortamı çalışmıyor olabilir)"
fi

# 3. PROD Media Backup
log "PROD media dosyaları yedekleniyor..."
if [ -d "/app/media" ] && [ "$(ls -A /app/media)" ]; then
    if tar czf "$BACKUP_DIR/media_prod_$DATE.tar.gz" -C /app/media . 2>>"$LOG_FILE"; then
        MEDIA_SIZE=$(du -h "$BACKUP_DIR/media_prod_$DATE.tar.gz" | cut -f1)
        log_success "PROD media yedeklendi: $MEDIA_SIZE"
    else
        log_error "PROD media yedekleme başarısız!"
    fi
else
    log_warning "PROD media dizini bulunamadı veya boş"
fi

# 4. DEV Media Backup
log "DEV media dosyaları yedekleniyor..."
if [ -d "/app/media_dev" ] && [ "$(ls -A /app/media_dev)" ]; then
    if tar czf "$BACKUP_DIR/media_dev_$DATE.tar.gz" -C /app/media_dev . 2>>"$LOG_FILE"; then
        MEDIA_SIZE=$(du -h "$BACKUP_DIR/media_dev_$DATE.tar.gz" | cut -f1)
        log_success "DEV media yedeklendi: $MEDIA_SIZE"
    else
        log_warning "DEV media yedekleme başarısız"
    fi
else
    log_warning "DEV media dizini bulunamadı veya boş"
fi

# 5. Website Media Backup
log "Website media dosyaları yedekleniyor..."
if [ -d "/app/website_media" ] && [ "$(ls -A /app/website_media)" ]; then
    if tar czf "$BACKUP_DIR/media_website_$DATE.tar.gz" -C /app/website_media . 2>>"$LOG_FILE"; then
        MEDIA_SIZE=$(du -h "$BACKUP_DIR/media_website_$DATE.tar.gz" | cut -f1)
        log_success "Website media yedeklendi: $MEDIA_SIZE"
    else
        log_warning "Website media yedekleme başarısız"
    fi
else
    log_warning "Website media dizini bulunamadı veya boş"
fi

# 6. Toplam backup boyutu
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "0")
log_success "Backup tamamlandı. Toplam boyut: $TOTAL_SIZE"

# 7. Eski backup'ları temizle (30 günden eski)
log "Eski backup'lar temizleniyor (30 günden eski)..."
find "$BACKUP_BASE_DIR" -type d -name "20*" -mtime +30 -exec rm -rf {} \; 2>/dev/null || true

log "=== Backup tamamlandı ===\n"

# Backup özeti oluştur
SUMMARY_FILE="$BACKUP_DIR/backup_summary.txt"
cat > "$SUMMARY_FILE" << EOF
Kuafora Backup Özeti
====================
Tarih: $(date '+%Y-%m-%d %H:%M:%S')
Backup Dizini: $BACKUP_DIR

Yedeklenen Dosyalar:
- PROD Veritabanı: db_prod_$DATE.sql.gz
- DEV Veritabanı: db_dev_$DATE.sql.gz
- PROD Media: media_prod_$DATE.tar.gz
- DEV Media: media_dev_$DATE.tar.gz
- Website Media: media_website_$DATE.tar.gz

Toplam Boyut: $TOTAL_SIZE
EOF

log_success "Backup özeti oluşturuldu: $SUMMARY_FILE"

