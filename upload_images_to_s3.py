#!/usr/bin/env python3
"""
Görselleri S3'e yükleme scripti
AWS CLI sorunları için Python boto3 kullanır
"""

import boto3
import os
import sys
from pathlib import Path
from botocore.exceptions import ClientError, BotoCoreError

BUCKET_NAME = "kuafora-website"
REGION = "eu-central-1"

def upload_file(s3_client, local_path, s3_key):
    """Tek bir dosyayı S3'e yükle"""
    try:
        print(f"📤 Yükleniyor: {local_path} -> s3://{BUCKET_NAME}/{s3_key}")
        s3_client.upload_file(
            local_path,
            BUCKET_NAME,
            s3_key,
            ExtraArgs={'ACL': 'public-read', 'ContentType': get_content_type(local_path)}
        )
        print(f"✅ Yüklendi: {s3_key}")
        return True
    except Exception as e:
        print(f"❌ Hata ({local_path}): {e}")
        return False

def get_content_type(file_path):
    """Dosya tipine göre Content-Type döndür"""
    ext = Path(file_path).suffix.lower() = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
    }
    return content_types.get(ext, 'application/octet-stream')

def upload_directory(s3_client, local_dir, s3_prefix):
    """Bir dizindeki tüm dosyaları S3'e yükle"""
    local_path = Path(local_dir)
    
    if not local_path.exists():
        print(f"⚠️  Dizin bulunamadı: {local_dir}")
        return False
    
    uploaded_count = 0
    failed_count = 0
    
    # Tüm dosyaları bul (alt dizinler dahil)
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            # Local path'i relative path'e çevir
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{s3_prefix}/{relative_path}".replace('\\', '/')
            
            if upload_file(s3_client, str(file_path), s3_key):
                uploaded_count += 1
            else:
                fail 1
    
    return uploaded_count, failed_count

def main():
    print("🚀 Görseller S3'e yükleniyor...")
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
    
    # S3 client oluştur
    try:
        s3_client = boto3.client('s3', region_name=REGION)
        print(f"✅ S3 client oluşturuldu (Region: {REGION})")
        print("")
    except Exception as e:
        print(f"❌ S3 client oluşturulamadı: {e}")
        sys.exit(1)
    
    # Static dizinini kontrol et
    static_dir = Path(__file__).parent / 'static' / 'img'
    
    if not static_dir.exists():
    ni bulunamadı: {static_dir}")
        print("   Lütfen görselleri şu dizine koyun: static/img/")
        sys.exit(1)
    
    print(f"📁 Kaynak dizin: {static_dir}")
    print(f"📦 Hedef bucket: {BUCKET_NAME}")
    print("")
    
    # Görselleri yükle
    uploaded, failed = upload_directory(s3_client, static_dir, 'static/img')
    
    print("")
    print("=" * 60)
    print("✅ Yükleme tamamlandı!")
    print("=" * 60)
    print(f"   ✅ Başarılı: {uploaded} dosya")
    if failed > 0:
        print(f"   ❌ Başarısız: {failed} dosya")
    print("")
    print(f"🌐 Görseller şurada: https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/static/img/")
    print("")

if __name__ == "__main__":
    main()
