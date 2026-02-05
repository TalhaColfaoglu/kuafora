# CloudFront Kurulum Komutları (SSH)

Bu doküman, SSH üzerinden CloudFront CDN kurulumu için gerekli tüm komutları içerir.

## 📋 Önkoşullar

1. SSH ile server'a bağlanın
2. AWS credentials'larınız hazır olmalı
3. S3 bucket zaten oluşturulmuş olmalı

## 🚀 Adım 1: Script'i Server'a Yükleyin

### Yerel bilgisayarınızdan:

```bash
# Script'i server'a kopyalayın
scp kuafora/kuafora-website/scripts/create_cloudfront_distribution.py user@your-server:/tmp/

# VEYA direkt server'da oluşturun
```

## 🔧 Adım 2: SSH'de CloudFront Distribution Oluşturun

### SSH ile server'a bağlanın:

```bash
ssh user@your-server
```

### Script'i çalıştırın:

```bash
# Website dizinine gidin
cd ~/kuafora/kuafora-website

# Script'i oluşturun (eğer yoksa)
cat > scripts/create_cloudfront_distribution.py << 'SCRIPT_EOF'
#!/usr/bin/env python3
"""
CloudFront Distribution Oluşturma Scripti
"""
import os
import sys
import json
import time
import boto3
from botocore.exceptions import ClientError

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'kuafora-website')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'eu-central-1')

cloudfront = boto3.client('cloudfront', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name='us-east-1')
s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_S3_REGION_NAME)

def check_s3_bucket():
    try:
        s3.head_bucket(Bucket=AWS_STORAGE_BUCKET_NAME)
        print(f"✅ S3 bucket '{AWS_STORAGE_BUCKET_NAME}' bulundu")
        return True
    except ClientError as e:
        print(f"❌ S3 bucket bulunamadı: {e}")
        return False

def create_origin_access_control():
    try:
        oac_name = f'{AWS_STORAGE_BUCKET_NAME}-oac'
        paginator = cloudfront.get_paginator('list_origin_access_controls')
        for page in paginator.paginate():
            for oac in page.get('OriginAccessControlList', {}).get('Items', []):
                if oac['Name'] == oac_name:
                    print(f"✅ OAC '{oac_name}' mevcut: {oac['Id']}")
                    return oac['Id']
        
        response = cloudfront.create_origin_access_control(
            OriginAccessControlConfig={
                'Name': oac_name,
                'Description': f'OAC for {AWS_STORAGE_BUCKET_NAME}',
                'SigningProtocol': 'sigv4',
                'SigningBehavior': 'always',
                'OriginAccessControlOriginType': 's3'
            }
        )
        oac_id = response['OriginAccessControl']['Id']
        print(f"✅ OAC oluşturuldu: {oac_id}")
        return oac_id
    except ClientError as e:
        print(f"❌ OAC oluşturma hatası: {e}")
        return None

def create_cloudfront_distribution():
    if not check_s3_bucket():
        return None
    
    oac_id = create_origin_access_control()
    if not oac_id:
        return None
    
    s3_domain = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
    
    try:
        distribution_config = {
            'CallerReference': f'{AWS_STORAGE_BUCKET_NAME}-{int(time.time())}',
            'Comment': f'CloudFront for {AWS_STORAGE_BUCKET_NAME}',
            'DefaultCacheBehavior': {
                'TargetOriginId': f'S3-{AWS_STORAGE_BUCKET_NAME}',
                'ViewerProtocolPolicy': 'redirect-to-https',
                'AllowedMethods': {'Quantity': 3, 'Items': ['GET', 'HEAD', 'OPTIONS'], 'CachedMethods': {'Quantity': 2, 'Items': ['GET', 'HEAD']}},
                'Compress': True,
                'CachePolicyId': '658327ea-f89d-4fab-a63d-7e88639e788f',
            },
            'Origins': {
                'Quantity': 1,
                'Items': [{
                    'Id': f'S3-{AWS_STORAGE_BUCKET_NAME}',
                    'DomainName': s3_domain,
                    'S3OriginConfig': {'OriginAccessIdentity': ''},
                    'OriginAccessControlId': oac_id
                }]
            },
            'Enabled': True,
            'PriceClass': 'PriceClass_100',
            'HttpVersion': 'http2and3',
            'IsIPV6Enabled': True,
        }
        
        response = cloudfront.create_distribution(DistributionConfig=distribution_config)
        distribution = response['Distribution']
        distribution_id = distribution['Id']
        distribution_domain = distribution['DomainName']
        
        print(f"\n✅ CloudFront Distribution oluşturuldu!")
        print(f"   Distribution ID: {distribution_id}")
        print(f"   Domain Name: {distribution_domain}")
        print(f"\n📝 Environment Variable:")
        print(f"   AWS_S3_CUSTOM_DOMAIN={distribution_domain}")
        
        return distribution_domain
    except ClientError as e:
        print(f"❌ CloudFront oluşturma hatası: {e}")
        return None

if __name__ == '__main__':
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        print("❌ AWS credentials bulunamadı!")
        sys.exit(1)
    
    print("🚀 CloudFront Distribution Oluşturuluyor...")
    create_cloudfront_distribution()
SCRIPT_EOF

# Script'e çalıştırma izni verin
chmod +x scripts/create_cloudfront_distribution.py

# Environment variables'ı ayarlayın (mevcut .env dosyanıza ekleyin)
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_STORAGE_BUCKET_NAME=kuafora-website
export AWS_S3_REGION_NAME=eu-central-1

# Script'i çalıştırın
python3 scripts/create_cloudfront_distribution.py
```

## 📝 Adım 3: Environment Variable Ekleyin

Script'in gösterdiği CloudFront domain'ini environment variable'a ekleyin:

```bash
# Örnek çıktı:
# Domain Name: d1234567890abc.cloudfront.net

# Docker Compose kullanıyorsanız .env dosyasına ekleyin
echo "AWS_S3_CUSTOM_DOMAIN=d1234567890abc.cloudfront.net" >> .env

# VEYA direkt export edin (geçici)
export AWS_S3_CUSTOM_DOMAIN=d1234567890abc.cloudfront.net

# VEYA systemd service dosyasına ekleyin
sudo nano /etc/systemd/system/kuafora-website.service
# Environment="AWS_S3_CUSTOM_DOMAIN=d1234567890abc.cloudfront.net" satırını ekleyin
```

## 🔄 Adım 4: Django Uygulamasını Yeniden Başlatın

### Docker Compose kullanıyorsanız:

```bash
# Environment variable'ı .env dosyasına ekledikten sonra
cd ~/kuafora
docker-compose restart website

# VEYA tamamen yeniden başlatın
docker-compose down
docker-compose up -d website
```

### Systemd kullanıyorsanız:

```bash
sudo systemctl daemon-reload
sudo systemctl restart kuafora-website
```

### Manuel olarak:

```bash
cd ~/kuafora/kuafora-website
source venv/bin/activate  # Virtual environment varsa
python manage.py collectstatic --noinput
# Uygulamanızı yeniden başlatın (gunicorn, uwsgi, vs.)
```

## ✅ Adım 5: Test Edin

```bash
# Django shell'de test edin
cd ~/kuafora/kuafora-website
python manage.py shell

# Shell'de:
from django.conf import settings
print(settings.STATIC_URL)
# Çıktı: https://d1234567890abc.cloudfront.net/static/ olmalı

# Browser'da test edin
# Website'i açın ve Developer Tools > Network sekmesinde görsellerin CloudFront'tan yüklendiğini kontrol edin
```

## 🔍 CloudFront Distribution Durumunu Kontrol Edin

```bash
# AWS CLI ile kontrol edin
aws cloudfront list-distributions --query "DistributionList.Items[*].[Id,DomainName,Status]" --output table

# Belirli bir distribution'ın durumunu kontrol edin
aws cloudfront get-distribution --id YOUR_DISTRIBUTION_ID --query "Distribution.Status" --output text
```

## 🗑️ Cache Invalidation (Görsel Güncelleme)

Görselleri güncellediğinizde CloudFront cache'ini temizleyin:

```bash
# Tüm static files için
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/static/*"

# Sadece görseller için
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/static/img/screens/*"
```

## 📊 Hızlı Kontrol Komutları

```bash
# Environment variable'ı kontrol edin
echo $AWS_S3_CUSTOM_DOMAIN

# Django settings'te kontrol edin
cd ~/kuafora/kuafora-website
python manage.py shell -c "from django.conf import settings; print('STATIC_URL:', settings.STATIC_URL)"

# CloudFront distribution listesi
aws cloudfront list-distributions --query "DistributionList.Items[*].[Id,DomainName,Status]" --output table

# S3 bucket kontrolü
aws s3 ls s3://kuafora-website/static/img/screens/
```

## 🐛 Sorun Giderme

### CloudFront domain çalışmıyor:

```bash
# Distribution durumunu kontrol edin
aws cloudfront get-distribution --id YOUR_DISTRIBUTION_ID

# Status "Deployed" olmalı (10-15 dakika sürebilir)
```

### Görseller yüklenmiyor:

```bash
# S3 bucket policy'yi kontrol edin
aws s3api get-bucket-policy --bucket kuafora-website

# CloudFront OAC'yi kontrol edin
aws cloudfront list-origin-access-controls
```

### Environment variable çalışmıyor:

```bash
# .env dosyasını kontrol edin
cat .env | grep AWS_S3_CUSTOM_DOMAIN

# Docker container içinde kontrol edin
docker exec -it kuafora-website env | grep AWS_S3_CUSTOM_DOMAIN
```

## 📝 Özet Komutlar (Tek Seferde)

```bash
# 1. Script'i oluştur ve çalıştır
cd ~/kuafora/kuafora-website
# (Script yukarıda verildi)

# 2. CloudFront domain'ini .env'e ekle
echo "AWS_S3_CUSTOM_DOMAIN=d1234567890abc.cloudfront.net" >> ~/kuafora/.env

# 3. Docker'ı yeniden başlat
cd ~/kuafora
docker-compose restart website

# 4. Test et
docker exec -it kuafora-website python manage.py shell -c "from django.conf import settings; print(settings.STATIC_URL)"
```

## 🎯 Sonuç

Bu komutları çalıştırdıktan sonra:
- ✅ Görseller CloudFront CDN üzerinden yüklenecek
- ✅ Daha hızlı yükleme
- ✅ Daha düşük maliyet
- ✅ Global performans
