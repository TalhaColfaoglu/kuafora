#!/usr/bin/env python3
"""
CloudFront Distribution Oluşturma Scripti
Bu script, Kuafora website görselleri için CloudFront CDN distribution oluşturur.

Kullanım:
    python scripts/create_cloudfront_distribution.py

Gereksinimler:
    - AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - boto3 paketi: pip install boto3
    - S3 bucket'ın zaten oluşturulmuş olması
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError

# AWS Credentials
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'kuafora-website')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'eu-central-1')

# CloudFront client
cloudfront = boto3.client(
    'cloudfront',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name='us-east-1'  # CloudFront her zaman us-east-1'de
)

# S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION_NAME
)


def check_s3_bucket():
    """S3 bucket'ın var olup olmadığını kontrol et"""
    try:
        s3.head_bucket(Bucket=AWS_STORAGE_BUCKET_NAME)
        print(f"✅ S3 bucket '{AWS_STORAGE_BUCKET_NAME}' bulundu")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"❌ S3 bucket '{AWS_STORAGE_BUCKET_NAME}' bulunamadı!")
            print(f"   Lütfen önce S3 bucket'ı oluşturun.")
            return False
        else:
            print(f"❌ S3 bucket kontrolü başarısız: {e}")
            return False


def create_origin_access_control():
    """Origin Access Control (OAC) oluştur"""
    try:
        oac_name = f'{AWS_STORAGE_BUCKET_NAME}-oac'
        
        # Mevcut OAC'leri kontrol et
        paginator = cloudfront.get_paginator('list_origin_access_controls')
        for page in paginator.paginate():
            for oac in page.get('OriginAccessControlList', {}).get('Items', []):
                if oac['Name'] == oac_name:
                    print(f"✅ Origin Access Control '{oac_name}' zaten mevcut")
                    return oac['Id']
        
        # Yeni OAC oluştur
        response = cloudfront.create_origin_access_control(
            OriginAccessControlConfig={
                'Name': oac_name,
                'Description': f'Origin Access Control for {AWS_STORAGE_BUCKET_NAME}',
                'SigningProtocol': 'sigv4',
                'SigningBehavior': 'always',
                'OriginAccessControlOriginType': 's3'
            }
        )
        oac_id = response['OriginAccessControl']['Id']
        print(f"✅ Origin Access Control '{oac_name}' oluşturuldu: {oac_id}")
        return oac_id
        
    except ClientError as e:
        print(f"❌ Origin Access Control oluşturma hatası: {e}")
        return None


def update_s3_bucket_policy(oac_id, distribution_arn):
    """S3 bucket policy'yi CloudFront OAC için güncelle"""
    import json
    import boto3
    
    try:
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowCloudFrontServicePrincipal",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "cloudfront.amazonaws.com"
                    },
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{AWS_STORAGE_BUCKET_NAME}/*",
                    "Condition": {
                        "StringEquals": {
                            "AWS:SourceArn": distribution_arn
                        }
                    }
                }
            ]
        }
        
        s3.put_bucket_policy(
            Bucket=AWS_STORAGE_BUCKET_NAME,
            Policy=json.dumps(bucket_policy)
        )
        print(f"✅ S3 bucket policy güncellendi")
        return True
        
    except ClientError as e:
        print(f"⚠️  S3 bucket policy güncelleme hatası: {e}")
        print(f"   Manuel olarak bucket policy'yi güncellemeniz gerekebilir.")
        return False


def create_cloudfront_distribution():
    """CloudFront distribution oluştur"""
    import time
    import json
    import boto3
    
    try:
        # S3 bucket kontrolü
        if not check_s3_bucket():
            return None
        
        # Origin Access Control oluştur
        oac_id = create_origin_access_control()
        if not oac_id:
            return None
        
        # S3 origin domain
        s3_domain = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
        
        # CloudFront distribution oluştur
        distribution_config = {
            'CallerReference': f'{AWS_STORAGE_BUCKET_NAME}-{int(time.time())}',
            'Comment': f'CloudFront distribution for {AWS_STORAGE_BUCKET_NAME} static files',
            'DefaultCacheBehavior': {
                'TargetOriginId': f'S3-{AWS_STORAGE_BUCKET_NAME}',
                'ViewerProtocolPolicy': 'redirect-to-https',
                'AllowedMethods': {
                    'Quantity': 3,
                    'Items': ['GET', 'HEAD', 'OPTIONS'],
                    'CachedMethods': {
                        'Quantity': 2,
                        'Items': ['GET', 'HEAD']
                    }
                },
                'Compress': True,
                'CachePolicyId': '658327ea-f89d-4fab-a63d-7e88639e788f',  # CachingOptimized
                'OriginRequestPolicyId': '88a5eaf4-2fd4-4709-b370-b4c650ea3fcf',  # CORS-S3Origin
            },
            'Origins': {
                'Quantity': 1,
                'Items': [
                    {
                        'Id': f'S3-{AWS_STORAGE_BUCKET_NAME}',
                        'DomainName': s3_domain,
                        'S3OriginConfig': {
                            'OriginAccessIdentity': ''
                        },
                        'OriginAccessControlId': oac_id
                    }
                ]
            },
            'Enabled': True,
            'PriceClass': 'PriceClass_100',  # North America and Europe
            'HttpVersion': 'http2and3',
            'IsIPV6Enabled': True,
        }
        
        response = cloudfront.create_distribution(DistributionConfig=distribution_config)
        distribution = response['Distribution']
        distribution_id = distribution['Id']
        distribution_domain = distribution['DomainName']
        
        # AWS Account ID'yi al
        sts = boto3.client('sts', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
        account_id = sts.get_caller_identity()['Account']
        
        print(f"\n✅ CloudFront Distribution oluşturuldu!")
        print(f"   Distribution ID: {distribution_id}")
        print(f"   Domain Name: {distribution_domain}")
        print(f"\n📝 Environment Variable:")
        print(f"   AWS_S3_CUSTOM_DOMAIN={distribution_domain}")
        print(f"\n⏳ Distribution'ın deploy edilmesi 10-15 dakika sürebilir.")
        print(f"   Status: {distribution['Status']}")
        
        # S3 bucket policy'yi güncelle
        distribution_arn = f"arn:aws:cloudfront::{account_id}:distribution/{distribution_id}"
        update_s3_bucket_policy(oac_id, distribution_arn)
        
        return distribution_domain
        
    except ClientError as e:
        print(f"❌ CloudFront distribution oluşturma hatası: {e}")
        return None
    except Exception as e:
        print(f"❌ Beklenmeyen hata: {e}")
        return None


if __name__ == '__main__':
    import json
    import time
    
    print("🚀 CloudFront Distribution Oluşturma Scripti")
    print("=" * 50)
    
    # AWS credentials kontrolü
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        print("❌ AWS credentials bulunamadı!")
        print("   Lütfen AWS_ACCESS_KEY_ID ve AWS_SECRET_ACCESS_KEY environment variable'larını ayarlayın.")
        sys.exit(1)
    
    print(f"📦 S3 Bucket: {AWS_STORAGE_BUCKET_NAME}")
    print(f"🌍 Region: {AWS_S3_REGION_NAME}")
    print()
    
    # CloudFront distribution oluştur
    distribution_domain = create_cloudfront_distribution()
    
    if distribution_domain:
        print(f"\n✅ Başarılı! CloudFront distribution hazır.")
        print(f"\n📋 Sonraki Adımlar:")
        print(f"   1. Environment variable'ı ayarlayın:")
        print(f"      export AWS_S3_CUSTOM_DOMAIN={distribution_domain}")
        print(f"   2. Django uygulamasını yeniden başlatın")
        print(f"   3. Görsellerin CloudFront'tan yüklendiğini test edin")
    else:
        print(f"\n❌ CloudFront distribution oluşturulamadı!")
        sys.exit(1)
