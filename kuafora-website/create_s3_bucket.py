#!/usr/bin/env python3
"""
Kuafora Website S3 Bucket Oluşturma Scripti
AWS CLI sorunları için Python boto3 kullanır
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError, BotoCoreError

BUCKET_NAME = "kuafora-website"
REGION = "eu-central-1"

def create_bucket():
    """S3 bucket oluştur"""
    try:
        s3_client = boto3.client('s3', region_name=REGION)
        
        # Bucket oluştur
        print(f"📦 Bucket oluşturuluyor: {BUCKET_NAME}")
        
        # eu-central-1 için location constraint gerekli
        s3_client.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={'LocationConstraint': REGION}
        )
        print(f"✅ Bucket oluşturuldu: {BUCKET_NAME}")
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'BucketAlreadyExists':
            print(f"⚠️  Bucket zaten mevcut: {BUCKET_NAME}")
            return True
        elif error_code == 'BucketAlreadyOwnedByYou':
            print(f"✅ Bucket zaten sizin: {BUCKET_NAME}")
            return True
        else:
            print(f"❌ Bucket oluşturulamadı: {e}")
            return False
    except BotoCoreError as e:
        print(f"❌ AWS bağlantı hatası: {e}")
        print("   AWS credentials kontrol edin: aws configure")
        return False

def configure_public_access():
    """Public access ayarlarını yapılandır"""
    try:
        s3_client = boto3.client('s3')
        print("🔓 Public access ayarları yapılandırılıyor...")
        
        s3_client.put_public_access_block(
            Bucket=BUCKET_NAME,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': False,
                'IgnorePublicAcls': False,
                'BlockPublicPolicy': False,
                'RestrictPublicBuckets': False
            }
        )
        print("✅ Public access ayarları yapılandırıldı")
        return True
    except Exception as e:
        print(f"⚠️  Public access ayarları yapılandırılamadı: {e}")
        return False

def add_bucket_policy():
    """Bucket policy ekle (public read için)"""
    try:
        s3_client = boto3.client('s3')
        print("📋 Bucket policy ekleniyor...")
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{BUCKET_NAME}/*"
                }
            ]
        }
        
        s3_client.put_bucket_policy(
            Bucket=BUCKET_NAME,
            Policy=json.dumps(policy)
        )
        print("✅ Bucket policy eklendi")
        return True
    except Exception as e:
        print(f"⚠️  Bucket policy eklenemedi: {e}")
        return False

def add_cors_configuration():
    """CORS yapılandırması ekle"""
    try:
        s3_client = boto3.client('s3')
        print("🌐 CORS yapılandırması ekleniyor...")
        
        cors_config = {
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['GET', 'HEAD'],
                    'AllowedOrigins': ['*'],
                    'ExposeHeaders': [],
                    'MaxAgeSeconds': 3000
                }
            ]
        }
        
        s3_client.put_bucket_cors(
            Bucket=BUCKET_NAME,
            CORSConfiguration=cors_config
        )
        print("✅ CORS yapılandırması eklendi")
        return True
    except Exception as e:
        print(f"⚠️  CORS yapılandırması eklenemedi: {e}")
        return False

def create_folder_structure():
    """Klasör yapısını oluştur"""
    try:
        s3_client = boto3.client('s3')
        print("📁 Klasör yapısı oluşturuluyor...")
        
        folders = [
            'static/img/',
            'static/img/screens/',
            'media/'
        ]
        
        for folder in folders:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=folder,
                Body=b''
            )
        
        print("✅ Klasör yapısı oluşturuldu")
        return True
    except Exception as e:
        print(f"⚠️  Klasör yapısı oluşturulamadı: {e}")
        return False

def main():
    print("🚀 Kuafora Website S3 Bucket oluşturuluyor...")
    print("")
    
    # AWS credentials kontrolü
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        if not credentials:
            print("❌ AWS credentials bulunamadı!")
            print("   Lütfen şu komutu çalıştırın: aws configure")
            sys.exit(1)
        print(f"✅ AWS credentials bulundu")
        print("")
    except Exception as e:
        print(f"❌ AWS credentials kontrol edilemedi: {e}")
        sys.exit(1)
    
    # Bucket oluştur
    if not create_bucket():
        sys.exit(1)
    
    print("")
    
    # Yapılandırmaları uygula
    configure_public_access()
    add_bucket_policy()
    add_cors_configuration()
    create_folder_structure()
    
    print("")
    print("=" * 60)
    print("✅ S3 Bucket başarıyla oluşturuldu ve yapılandırıldı!")
    print("=" * 60)
    print("")
    print("📋 Bucket Bilgileri:")
    print(f"   Bucket Name: {BUCKET_NAME}")
    print(f"   Region: {REGION}")
    print(f"   URL: https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com")
    print("")
    print("📝 Sonraki Adımlar:")
    print("   1. Environment variables'a ekle:")
    print(f"      AWS_STORAGE_BUCKET_NAME={BUCKET_NAME}")
    print(f"      AWS_S3_REGION_NAME={REGION}")
    print("")
    print("   2. Görselleri yüklemek için:")
    print(f"      aws s3 sync static/img/ s3://{BUCKET_NAME}/static/img/ --acl public-read")
    print("")
    print("   3. Django collectstatic çalıştır:")
    print("      python manage.py collectstatic --noinput")
    print("")

if __name__ == "__main__":
    main()
