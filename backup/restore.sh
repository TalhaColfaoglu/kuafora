#!/bin/bash
# Kuafora Backup Geri Yükleme Script'i
# Kullanım: ./restore.sh <backup_tarihi> [db|media|all]
# Örnek: ./restore.sh 20241201_120000 all

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKUP_BASE_DIR="/backups/kuafora"
BACKUP_DATE=$1
RESTORE_TYPE=${2:-all}  # db, media, veya all

if [ -z "$BACKUP_DATE" ]; then
    echo -e "${RED}Kullanım: $0 <backup_tarihi> [db|media|all]${NC}"
    echo "Örnek: $0 20241201_120000 all"
    echo ""
    echo "Mevcut backup'lar:"
    ls -1 "$BACKUP_BASE_DIR" | grep "^20" || echo "Backup bulunamadı"
    exit 1
fi

BACKUP_DIR="$BACKUP_BASE_DIR/$BACKUP_DATE"

if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}Backup dizini bulunamadı: $BACKUP_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}=== Backup Geri Yükleme ===${NC}"
echo "Backup Tarihi: $BACKUP_DATE"
echo "Yüklenecek: $RESTORE_TYPE"
echo ""

# Veritabanı geri yükleme
if [ "$RESTORE_TYPE" = "db" ] || [ "$RESTORE_TYPE" = "all" ]; then
    echo -e "${YELLOW}PROD veritabanı geri yükleniyor...${NC}"
    read -p "Bu işlem mevcut veritabanını SİLECEK! Devam etmek istiyor musunuz? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "İşlem iptal edildi"
        exit 0
    fi
    
    if [ -f "$BACKUP_DIR/db_prod_$BACKUP_DATE.sql.gz" ]; then
        echo "Backup dosyası açılıyor..."
        gunzip -c "$BACKUP_DIR/db_prod_$BACKUP_DATE.sql.gz" | docker compose exec -T db psql -U kuafora_user -d kuafora_db
        echo -e "${GREEN}PROD veritabanı geri yüklendi${NC}"
    else
        echo -e "${RED}PROD veritabanı backup dosyası bulunamadı${NC}"
    fi
fi

# Media geri yükleme
if [ "$RESTORE_TYPE" = "media" ] || [ "$RESTORE_TYPE" = "all" ]; then
    echo -e "${YELLOW}Media dosyaları geri yükleniyor...${NC}"
    read -p "Bu işlem mevcut media dosyalarını SİLECEK! Devam etmek istiyor musunuz? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "İşlem iptal edildi"
        exit 0
    fi
    
    if [ -f "$BACKUP_DIR/media_prod_$BACKUP_DATE.tar.gz" ]; then
        echo "PROD media geri yükleniyor..."
        docker run --rm \
            -v kuafora_backend_media:/data \
            -v "$BACKUP_DIR":/backup \
            alpine sh -c "cd /data && rm -rf * && tar xzf /backup/media_prod_$BACKUP_DATE.tar.gz"
        echo -e "${GREEN}PROD media geri yüklendi${NC}"
    else
        echo -e "${RED}PROD media backup dosyası bulunamadı${NC}"
    fi
fi

echo -e "${GREEN}=== Geri Yükleme Tamamlandı ===${NC}"

