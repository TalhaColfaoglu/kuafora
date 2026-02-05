#!/bin/bash

# Kuafora Website S3 Bucket Oluşturma Scripti
# Bu script S3 bucket'ını oluşturur ve gerekli yapılandırmaları yapar

BUCKET_NAME="kuafora-website"
REGION="eu-west-1"

echo "🚀 Kuafora Website S3 Bucket oluşturuluyor..."

# 1. Bucket oluştur
echo "📦 Bucket oluşturuluyor: $BUCKET_NAME"
aws s3 mb s3://$BUCKET_NAME --region $REGION

if [ $? -ne 0 ]; then
    echo "❌ Bucket oluşturulamadı. Bucket zaten var olabilir veya AWS credentials eksik."
    exit 1
fi

echo "✅ Bucket oluşturuldu: $BUCKET_NAME"

# 2. Public access ayarlarını yapılandır
echo "🔓 Public access ayarları yapılandırılıyor..."
aws s3api put-public-access-block \
    --bucket $BUCKET_NAME \
    --public-access-block-configuration \
    "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# 3. Bucket policy ekle (public read için)
echo "📋 Bucket policy ekleniyor..."
cat > /tmp/bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file:///tmp/bucket-policy.json
rm /tmp/bucket-policy.json

# 4. CORS yapılandırması ekle
echo "🌐 CORS yapılandırması ekleniyor..."
cat > /tmp/cors-config.json << EOF
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": [],
            "MaxAgeSeconds": 3000
        }
    ]
}
EOF

aws s3api put-bucket-cors --bucket $BUCKET_NAME --cors-configuration file:///tmp/cors-config.json
rm /tmp/cors-config.json

# 5. Website yapılandırması (opsiyonel - static website hosting için)
echo "🌍 Website yapılandırması ekleniyor..."
cat > /tmp/website-config.json << EOF
{
    "IndexDocument": {
        "Suffix": "index.html"
    },
    "ErrorDocument": {
        "Key": "error.html"
    }
}
EOF

aws s3api put-bucket-website --bucket $BUCKET_NAME --website-configuration file:///tmp/website-config.json
rm /tmp/website-config.json

# 6. Versioning'i etkinleştir (opsiyonel)
echo "📝 Versioning etkinleştiriliyor..."
aws s3api put-bucket-versioning \
    --bucket $BUCKET_NAME \
    --versioning-configuration Status=Enabled

# 7. Klasör yapısını oluştur
echo "📁 Klasör yapısı oluşturuluyor..."
aws s3api put-object --bucket $BUCKET_NAME --key static/img/
aws s3api put-object --bucket $BUCKET_NAME --key static/img/screens/
aws s3api put-object --bucket $BUCKET_NAME --key media/

echo ""
echo "✅ S3 Bucket başarıyla oluşturuldu ve yapılandırıldı!"
echo ""
echo "📋 Bucket Bilgileri:"
echo "   Bucket Name: $BUCKET_NAME"
echo "   Region: $REGION"
echo "   URL: https://$BUCKET_NAME.s3.$REGION.amazonaws.com"
echo ""
echo "📝 Sonraki Adımlar:"
echo "   1. Environment variables'a ekle:"
echo "      AWS_STORAGE_BUCKET_NAME=$BUCKET_NAME"
echo "      AWS_S3_REGION_NAME=$REGION"
echo ""
echo "   2. Görselleri yüklemek için:"
echo "      aws s3 sync static/img/ s3://$BUCKET_NAME/static/img/ --acl public-read"
echo ""
echo "   3. Django collectstatic çalıştır:"
echo "      python manage.py collectstatic --noinput"
