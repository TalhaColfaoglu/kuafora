# AWS CloudWatch Dashboard - EC2 Server Monitoring Rehberi

Bu rehber, EC2 server'ınızın durumunu (CPU, Memory, Disk, Network) CloudWatch dashboard'larında görüntülemek için gereken adımları içerir.

## 📊 Dashboard Oluşturma (AWS Console)

### 1. CloudWatch Dashboard'a Gitme

1. **AWS Console** → **CloudWatch** → **Dashboards**
2. **Create dashboard** butonuna tıklayın
3. Dashboard adı: `Kuafora-Server-Monitoring` (veya istediğiniz isim)

### 2. EC2 Instance'ınızı Bulma

1. **EC2 Console** → **Instances**
2. Instance ID'nizi not edin (örn: `i-0123456789abcdef0`)
3. Instance'ın **Name** tag'ini kontrol edin (varsa)

### 3. Widget'ları Ekleme

#### Widget 1: CPU Utilization (CPU Kullanımı)

1. Dashboard'da **Add widget** → **Line** seçin
2. **Metrics** tab'ına gidin
3. **AWS Namespaces** → **EC2** seçin
4. **Per-Instance Metrics** → **CPUUtilization** seçin
5. Instance'ınızı seçin (Instance ID veya Name tag ile)
6. **Graphed metrics**:
   - **Statistic**: `Average`
   - **Period**: `5 minutes` (veya `1 minute` daha detaylı için)
7. **Widget title**: `CPU Utilization (%)`
8. **Create widget**

#### Widget 2: Network In/Out (Ağ Trafiği)

1. **Add widget** → **Line** seçin
2. **Metrics** → **EC2** → **NetworkIn** ve **NetworkOut** seçin
3. Instance'ınızı seçin
4. **Statistic**: `Sum`
5. **Period**: `5 minutes`
6. **Widget title**: `Network Traffic (Bytes)`
7. **Create widget**

#### Widget 3: Disk Read/Write Operations

1. **Add widget** → **Line** seçin
2. **Metrics** → **EC2** → **DiskReadOps** ve **DiskWriteOps** seçin
3. Instance'ınızı seçin
4. **Statistic**: `Sum`
5. **Period**: `5 minutes`
6. **Widget title**: `Disk I/O Operations`
7. **Create widget**

#### Widget 4: Status Check Failed (Instance Health)

1. **Add widget** → **Number** seçin
2. **Metrics** → **EC2** → **StatusCheckFailed** seçin
3. Instance'ınızı seçin
4. **Statistic**: `Maximum`
5. **Period**: `1 minute`
6. **Widget title**: `Status Check Failed (1 = Failed, 0 = OK)`
7. **Create widget**

### 4. Detaylı Sistem Metrikleri İçin CloudWatch Agent Kurulumu

EC2 instance'ınızda **Memory**, **Disk Space**, **Process** gibi detaylı metrikleri görmek için CloudWatch agent kurmanız gerekir.

#### A. IAM Role Oluşturma (EC2 için)

1. **IAM Console** → **Roles** → **Create role**
2. **Trusted entity type**: `AWS service`
3. **Use case**: `EC2`
4. **Next**
5. **Permissions**: `CloudWatchAgentServerPolicy` seçin
6. Role adı: `Kuafora-EC2-CloudWatch-Role`
7. **Create role**

#### B. EC2 Instance'a IAM Role Atama

1. **EC2 Console** → **Instances** → Instance'ınızı seçin
2. **Actions** → **Security** → **Modify IAM role**
3. Oluşturduğunuz role'ü seçin: `Kuafora-EC2-CloudWatch-Role`
4. **Update IAM role**

#### C. CloudWatch Agent Kurulumu (SSH'de)

SSH ile EC2 instance'ınıza bağlanın ve şu komutları çalıştırın:

```bash
# CloudWatch agent'ı indir
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb

# Agent'ı kur
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

# Agent konfigürasyon dosyasını oluştur
sudo nano /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

#### D. Agent Konfigürasyon Dosyası

`/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json` dosyasına şu içeriği ekleyin:

```json
{
    "agent": {
        "metrics_collection_interval": 60,
        "run_as_user": "cwagent"
    },
    "metrics": {
        "namespace": "CWAgent",
        "metrics_collected": {
            "cpu": {
                "measurement": [
                    "cpu_usage_idle",
                    "cpu_usage_iowait",
                    "cpu_usage_user",
                    "cpu_usage_system"
                ],
                "totalcpu": false
            },
            "disk": {
                "measurement": [
                    "used_percent"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "*"
                ]
            },
            "diskio": {
                "measurement": [
                    "io_time"
                ],
                "resources": [
                    "*"
                ]
            },
            "mem": {
                "measurement": [
                    "mem_used_percent"
                ]
            },
            "netstat": {
                "measurement": [
                    "tcp_established",
                    "tcp_time_wait"
                ]
            },
            "processes": {
                "measurement": [
                    "running",
                    "sleeping",
                    "dead"
                ]
            }
        }
    }
}
```

#### E. Agent'ı Başlatma

```bash
# Agent'ı başlat
sudo systemctl start amazon-cloudwatch-agent

# Agent'ın çalıştığını kontrol et
sudo systemctl status amazon-cloudwatch-agent

# Agent'ı otomatik başlatmak için enable et
sudo systemctl enable amazon-cloudwatch-agent
```

#### F. Agent Metriklerini Dashboard'a Ekleme

1. **CloudWatch Dashboard** → **Add widget**
2. **Metrics** → **Custom Namespaces** → **CWAgent** seçin
3. Şu metrikleri ekleyin:
   - **Memory**: `mem_used_percent`
   - **Disk**: `disk_used_percent` (her disk için)
   - **CPU**: `cpu_usage_idle`, `cpu_usage_user`, `cpu_usage_system`

## 📈 Örnek Dashboard Yapısı

### Üst Satır (Sistem Durumu)
- **CPU Utilization** (Line chart)
- **Memory Usage** (Line chart)
- **Disk Usage** (Line chart)
- **Status Check** (Number widget)

### Alt Satır (Ağ ve I/O)
- **Network In/Out** (Line chart)
- **Disk Read/Write Ops** (Line chart)
- **Process Count** (Line chart)

## 🔔 Alarm Oluşturma

### CPU Alarm Örneği

1. **CloudWatch** → **Alarms** → **Create alarm**
2. **Select metric** → **EC2** → **CPUUtilization**
3. Instance'ınızı seçin
4. **Conditions**:
   - **Threshold type**: `Static`
   - **Whenever CPUUtilization is**: `Greater than 80`
   - **Period**: `5 minutes`
5. **Notification**: SNS topic oluşturun veya mevcut birini seçin
6. **Alarm name**: `Kuafora-High-CPU`
7. **Create alarm**

### Memory Alarm Örneği (CloudWatch Agent ile)

1. **CloudWatch** → **Alarms** → **Create alarm**
2. **Select metric** → **CWAgent** → **mem_used_percent**
3. **Conditions**:
   - **Threshold type**: `Static`
   - **Whenever mem_used_percent is**: `Greater than 85`
4. **Alarm name**: `Kuafora-High-Memory`
5. **Create alarm**

## 📊 Dashboard'u Paylaşma

1. Dashboard'da **Actions** → **Share dashboard**
2. **Public read-only** seçeneğini işaretleyin (isteğe bağlı)
3. **Share URL**'i kopyalayın

## 💡 İpuçları

1. **Auto-refresh**: Dashboard'da **Actions** → **Auto-refresh** → `1 minute` seçin
2. **Time range**: Dashboard'da zaman aralığını ayarlayın (örn: `Last 1 hour`)
3. **Widget size**: Widget'ları sürükleyerek boyutlandırabilirsiniz
4. **Multiple instances**: Birden fazla EC2 instance'ınız varsa, her birini ayrı widget'larda gösterebilirsiniz

## 🔧 Troubleshooting

### Metrikler görünmüyor

1. **EC2 Console** → **Instances** → Instance'ınızı seçin
2. **Monitoring** tab'ını kontrol edin
3. **Detailed monitoring** aktif mi kontrol edin (ücretli, isteğe bağlı)

### CloudWatch Agent çalışmıyor

```bash
# Agent loglarını kontrol et
sudo tail -f /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log

# Agent'ı yeniden başlat
sudo systemctl restart amazon-cloudwatch-agent

# IAM role'ün doğru atandığını kontrol et
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

### IAM Role atanamıyor

- EC2 instance'ı durdurulmuş olmalı (stop → modify IAM role → start)
- Veya yeni bir instance oluştururken IAM role'ü seçin

## 💰 Maliyet

- **Basic monitoring**: Ücretsiz (5 dakika aralık)
- **Detailed monitoring**: $0.015 per instance/hour (1 dakika aralık)
- **CloudWatch Agent metrikleri**: Standart CloudWatch fiyatlandırması
- **Dashboard'lar**: Ücretsiz

## 📝 Sonuç

CloudWatch dashboard'unuz hazır! Artık EC2 server'ınızın durumunu gerçek zamanlı olarak izleyebilirsiniz.

Sorularınız için: kuafora@outlook.com

