#!/bin/bash
# Kuafora Otomatik Backup Script
# Bu script günlük olarak veritabanı ve media dosyalarını yedekler

set -e  # Hata durumunda dur

# Renkler (loglar için)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backup dizinleri
BACKUP_BASE_DIR="/backups/kuafora"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/$DATE"

# Log dosyası
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

# Backup dizinini oluştur
mkdir -p "$BACKUP_DIR"

log "=== Backup başlatıldı ==="

# 1. PROD Veritabanı Backup
log "PROD veritabanı yedekleniyor..."
# Docker compose içinde çalışıyorsak direkt pg_dump kullan, değilse docker compose exec kullan
if command -v docker &> /dev/null && docker ps | grep -q kuafora_db; then
    # Docker container içinde çalışıyoruz veya docker compose var
    if docker compose exec -T db pg_dump -U kuafora_backend_user kuafora_backend > "$BACKUP_DIR/db_prod_$DATE.sql" 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
else
    # Direkt pg_dump (container içinde)
    if pg_dump -U kuafora_backend_user -h db kuafora_backend > "$BACKUP_DIR/db_prod_$DATE.sql" 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
fi

if [ "$BACKUP_CMD_SUCCESS" = true ]; then
    # Backup dosyasını sıkıştır
    gzip "$BACKUP_DIR/db_prod_$DATE.sql"
    DB_SIZE=$(du -h "$BACKUP_DIR/db_prod_$DATE.sql.gz" | cut -f1)
    log_success "PROD veritabanı yedeklendi: $DB_SIZE"
else
    log_error "PROD veritabanı yedekleme başarısız!"
    exit 1
fi

# 2. DEV Veritabanı Backup
log "DEV veritabanı yedekleniyor..."
if command -v docker &> /dev/null && docker ps | grep -q kuafora_db_dev; then
    if docker compose exec -T db_dev pg_dump -U kuafora_backend_user kuafora_backend > "$BACKUP_DIR/db_dev_$DATE.sql" 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
else
    if pg_dump -U kuafora_backend_user -h db_dev kuafora_backend > "$BACKUP_DIR/db_dev_$DATE.sql" 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
fi

if [ "$BACKUP_CMD_SUCCESS" = true ]; then
    gzip "$BACKUP_DIR/db_dev_$DATE.sql"
    DB_SIZE=$(du -h "$BACKUP_DIR/db_dev_$DATE.sql.gz" | cut -f1)
    log_success "DEV veritabanı yedeklendi: $DB_SIZE"
else
    log_warning "DEV veritabanı yedekleme başarısız (dev ortamı çalışmıyor olabilir)"
fi

# 3. PROD Media Backup
log "PROD media dosyaları yedekleniyor..."
if [ -d "/app/media" ]; then
    # Container içinde çalışıyoruz, direkt tar kullan
    if tar czf "$BACKUP_DIR/media_prod_$DATE.tar.gz" -C /app/media . 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
else
    # Docker compose ile çalışıyoruz
    if docker run --rm \
        -v kuafora_backend_media:/data:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf /backup/media_prod_$DATE.tar.gz -C /data . 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
fi

if [ "$BACKUP_CMD_SUCCESS" = true ]; then
    MEDIA_SIZE=$(du -h "$BACKUP_DIR/media_prod_$DATE.tar.gz" | cut -f1)
    log_success "PROD media yedeklendi: $MEDIA_SIZE"
else
    log_error "PROD media yedekleme başarısız!"
fi

# 4. DEV Media Backup
log "DEV media dosyaları yedekleniyor..."
if [ -d "/app/media_dev" ]; then
    if tar czf "$BACKUP_DIR/media_dev_$DATE.tar.gz" -C /app/media_dev . 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
else
    if docker run --rm \
        -v kuafora_backend_media_dev:/data:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf /backup/media_dev_$DATE.tar.gz -C /data . 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
fi

if [ "$BACKUP_CMD_SUCCESS" = true ]; then
    MEDIA_SIZE=$(du -h "$BACKUP_DIR/media_dev_$DATE.tar.gz" | cut -f1)
    log_success "DEV media yedeklendi: $MEDIA_SIZE"
else
    log_warning "DEV media yedekleme başarısız (dev ortamı çalışmıyor olabilir)"
fi

# 5. Website Media Backup
log "Website media dosyaları yedekleniyor..."
if [ -d "/app/website_media" ]; then
    if tar czf "$BACKUP_DIR/media_website_$DATE.tar.gz" -C /app/website_media . 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
else
    if docker run --rm \
        -v kuafora_website_media:/data:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf /backup/media_website_$DATE.tar.gz -C /data . 2>>"$LOG_FILE"; then
        BACKUP_CMD_SUCCESS=true
    else
        BACKUP_CMD_SUCCESS=false
    fi
fi

if [ "$BACKUP_CMD_SUCCESS" = true ]; then
    MEDIA_SIZE=$(du -h "$BACKUP_DIR/media_website_$DATE.tar.gz" | cut -f1)
    log_success "Website media yedeklendi: $MEDIA_SIZE"
else
    log_warning "Website media yedekleme başarısız"
fi

# 6. Toplam backup boyutu
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log_success "Backup tamamlandı. Toplam boyut: $TOTAL_SIZE"

# 7. Eski backup'ları temizle (30 günden eski)
log "Eski backup'lar temizleniyor (30 günden eski)..."
find "$BACKUP_BASE_DIR" -type d -name "20*" -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
DELETED_COUNT=$(find "$BACKUP_BASE_DIR" -type d -name "20*" -mtime +30 2>/dev/null | wc -l)
if [ "$DELETED_COUNT" -gt 0 ]; then
    log "Eski backup'lar temizlendi"
fi

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

