# AWS CloudWatch Kurulum Rehberi

Bu rehber, Kuafora backend uygulamasını AWS CloudWatch Logs ile entegre etmek için gereken adımları içerir.

## ✅ Yapılan Değişiklikler

1. ✅ `requirements.txt` - `watchtower==3.0.0` eklendi
2. ✅ `config/settings.py` - CloudWatch logging yapılandırması eklendi
3. ✅ `env/backend.env` - CloudWatch environment variables eklendi

## 📋 Yapmanız Gerekenler

### 1. AWS IAM Kullanıcı ve İzinler

#### A. IAM Kullanıcı Oluşturma (veya Mevcut Kullanıcıyı Kullanma)

1. AWS Console'a giriş yapın: https://console.aws.amazon.com
2. **IAM** servisine gidin
3. **Users** → **Create user** veya mevcut kullanıcıyı seçin
4. Kullanıcı adı: `kuafora-cloudwatch-user` (veya istediğiniz isim)

#### B. İzinleri Ayarlama

**Seçenek 1: Hazır Policy (Kolay)**
- **Attach policies directly** → `CloudWatchLogsFullAccess` seçin
- Bu policy tüm CloudWatch Logs işlemlerine izin verir

**Seçenek 2: Özel Policy (Daha Güvenli - Önerilen)**
- **Create policy** → JSON editor'ü açın
- Aşağıdaki policy'yi yapıştırın:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogStreams"
            ],
            "Resource": "arn:aws:logs:eu-central-1:*:log-group:kuafora-backend*"
        }
    ]
}
```

- Policy adı: `KuaforaCloudWatchLogsPolicy`
- Kullanıcıya bu policy'yi attach edin

#### C. Access Key Oluşturma

1. IAM → Users → Kullanıcınızı seçin
2. **Security credentials** tab'ına gidin
3. **Create access key** butonuna tıklayın
4. **Use case**: "Application running outside AWS" seçin
5. **Access Key ID** ve **Secret Access Key**'i kopyalayın ve güvenli bir yere kaydedin
   - ⚠️ **ÖNEMLİ**: Secret Access Key sadece bir kez gösterilir!

### 2. Environment Variables'ı Güncelleme

`env/backend.env` dosyasını düzenleyin:

```bash
# AWS CloudWatch Logs Configuration
AWS_CLOUDWATCH_ENABLED=True
AWS_CLOUDWATCH_LOG_GROUP_NAME=kuafora-backend
AWS_CLOUDWATCH_STREAM_NAME=api
AWS_CLOUDWATCH_REGION_NAME=eu-central-1

# AWS Credentials (CloudWatch için - S3 ile aynı key'leri kullanabilirsiniz)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE  # Gerçek Access Key ID'nizi yazın
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY  # Gerçek Secret Key'i yazın
```

**Not**: Eğer S3 için zaten AWS credentials kullanıyorsanız, aynı key'leri kullanabilirsiniz (yeterli izinleri varsa).

### 3. Backend'i Rebuild ve Restart Etme

```bash
cd /root/backend-frontend/kuafora

# Backend'leri rebuild et (watchtower paketi yüklenecek)
docker compose build --no-cache backend backend_dev

# Servisleri restart et
docker compose restart backend backend_dev

# Logları kontrol et
docker compose logs -f backend
```

### 4. CloudWatch'ta Kontrol Etme

1. AWS Console → **CloudWatch** → **Logs** → **Log groups**
2. `kuafora-backend` log group'unun oluştuğunu kontrol edin
3. Log group'u açın → `api` stream'ini kontrol edin
4. Loglar görünmeye başlamalı

### 5. Test Etme

```bash
# Backend container'ına gir
docker compose exec backend bash

# Python shell'de test log gönder
python manage.py shell
```

Python shell'de:

```python
import logging
logger = logging.getLogger('app')
logger.info("CloudWatch test log mesajı - Bu mesaj CloudWatch'ta görünmeli")
logger.error("CloudWatch test error mesajı")
```

CloudWatch Console'da logların göründüğünü kontrol edin.

## 🔧 Yapılandırma Seçenekleri

### Log Group ve Stream İsimlerini Değiştirme

`env/backend.env` dosyasında:

```bash
AWS_CLOUDWATCH_LOG_GROUP_NAME=kuafora-backend-prod  # Farklı isim
AWS_CLOUDWATCH_STREAM_NAME=api-prod  # Farklı stream
```

### CloudWatch'u Geçici Olarak Devre Dışı Bırakma

```bash
AWS_CLOUDWATCH_ENABLED=False
```

Bu durumda loglar sadece dosya ve console'a yazılır, CloudWatch'a gönderilmez.

### Farklı Region Kullanma

```bash
AWS_CLOUDWATCH_REGION_NAME=us-east-1  # Örnek: US East
```

## 📊 CloudWatch'ta Log Görüntüleme

1. **AWS Console** → **CloudWatch** → **Logs** → **Log groups**
2. `kuafora-backend` log group'unu seçin
3. Stream'leri görüntüleyin (örn: `api`)
4. Logları filtreleyebilir, arayabilir ve analiz edebilirsiniz

### Log Filtreleme Örnekleri

- **Hata logları**: `fields @message | filter @message like /ERROR/`
- **Belirli modül**: `fields @message | filter @module = "app.barbers"`
- **Zaman aralığı**: Log viewer'da tarih seçin

## 🔐 Güvenlik Notları

1. ✅ **Access Key'leri güvenli saklayın** - Kodda hardcode etmeyin
2. ✅ **IAM Policy'yi en az yetki ile sınırlayın** - Sadece gerekli izinleri verin
3. ✅ **Production'da IAM Role kullanın** (EC2/ECS için) - Access Key yerine
4. ✅ **Secret Access Key'i düzenli olarak rotate edin**

## 💰 Maliyet

- **CloudWatch Logs**: İlk 5 GB ücretsiz (aylık)
- **Log Storage**: $0.50 per GB (aylık)
- **Data Ingestion**: $0.50 per GB (aylık)

**Tahmini maliyet**: Küçük-orta trafikli bir uygulama için aylık $5-20 arası olabilir.

## 🐛 Troubleshooting

### Loglar CloudWatch'ta görünmüyor

1. **Credentials kontrolü**:
   ```bash
   docker compose exec backend python -c "
   import boto3
   client = boto3.client('logs', region_name='eu-central-1')
   print(client.describe_log_groups())
   "
   ```

2. **Environment variables kontrolü**:
   ```bash
   docker compose exec backend env | grep AWS
   ```

3. **Backend loglarını kontrol edin**:
   ```bash
   docker compose logs backend | grep -i cloudwatch
   ```

### "Access Denied" hatası

- IAM policy'de gerekli izinlerin olduğundan emin olun
- Access Key ID ve Secret Key'in doğru olduğunu kontrol edin

### "Log group not found" hatası

- Script otomatik olarak log group oluşturur, ancak izin yoksa başarısız olur
- Manuel olarak AWS Console'dan `kuafora-backend` log group'unu oluşturun

## 📝 Sonuç

CloudWatch kurulumu tamamlandı! Artık tüm backend logları AWS CloudWatch'ta merkezi olarak toplanıyor ve analiz edilebilir.

Sorularınız için: kuafora@outlook.com

