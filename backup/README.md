# Kuafora Otomatik Backup Sistemi

Bu sistem günlük olarak otomatik backup alır ve eski backup'ları temizler.

## 📁 Backup Yapısı

```
/backups/kuafora/
├── 20241201_120000/          # Her backup için tarihli klasör
│   ├── db_prod_20241201_120000.sql.gz
│   ├── db_dev_20241201_120000.sql.gz
│   ├── media_prod_20241201_120000.tar.gz
│   ├── media_dev_20241201_120000.tar.gz
│   ├── media_website_20241201_120000.tar.gz
│   └── backup_summary.txt
└── backup.log                # Tüm backup işlemlerinin logu
```

## 🚀 Kurulum

### 1. Backup script'lerini çalıştırılabilir yapın

```bash
chmod +x backup/backup.sh
chmod +x backup/restore.sh
```

### 2. Otomatik Backup Kurulumu (Cron Job)

#### Sunucuda (SSH ile bağlanın):

```bash
# Crontab'ı düzenle
crontab -e

# Aşağıdaki satırı ekleyin (her gün saat 02:00'de backup alır)
0 2 * * * cd /root/backend-frontend/kuafora && ./backup/backup.sh >> /backups/kuafora/cron.log 2>&1
```

#### Alternatif: Docker Container içinde Cron

`docker-compose.yml` dosyasına backup servisi ekleyebiliriz.

## 📋 Manuel Backup Alma

```bash
cd /root/backend-frontend/kuafora
./backup/backup.sh
```

## 🔄 Backup Geri Yükleme

### Tüm Backup'ı Geri Yükleme

```bash
cd /root/backend-frontend/kuafora
./backup/restore.sh 20241201_120000 all
```

### Sadece Veritabanını Geri Yükleme

```bash
./backup/restore.sh 20241201_120000 db
```

### Sadece Media Dosyalarını Geri Yükleme

```bash
./backup/restore.sh 20241201_120000 media
```

## 📊 Backup Listesi

Mevcut backup'ları görmek için:

```bash
ls -lh /backups/kuafora/
```

## 🗑️ Eski Backup'ları Temizleme

Script otomatik olarak 30 günden eski backup'ları siler. Manuel temizleme için:

```bash
# 30 günden eski backup'ları sil
find /backups/kuafora -type d -name "20*" -mtime +30 -exec rm -rf {} \;
```

## 📝 Log Dosyası

Tüm backup işlemleri `/backups/kuafora/backup.log` dosyasına kaydedilir.

## ⚠️ Önemli Notlar

1. **Backup dizini yeterli alana sahip olmalı**: Her backup yaklaşık 100-500 MB yer kaplayabilir
2. **Geri yükleme öncesi yedek alın**: Geri yükleme mevcut verileri siler!
3. **Backup'ları düzenli kontrol edin**: Log dosyasını kontrol ederek backup'ların başarılı olduğundan emin olun
4. **Offsite backup**: Güvenlik için backup'ları başka bir sunucuya veya buluta da kopyalayın

## 🔐 Güvenlik

- Backup dosyaları hassas veriler içerir, erişim izinlerini kontrol edin
- Backup'ları şifreleyebilirsiniz (opsiyonel)
- Backup dizinini sadece root kullanıcısının erişebileceği şekilde ayarlayın

## 📧 Bildirimler

Backup başarısız olursa email bildirimi eklemek için script'i güncelleyebilirsiniz.

