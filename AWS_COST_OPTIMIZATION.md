# 💰 AWS Maliyet Optimizasyonu Rehberi

Bu rehber, AWS paralı plana geçtikten sonra yapılması gereken maliyet optimizasyonlarını içerir.

## ✅ Kod Tarafında Yapılan Optimizasyonlar

Aşağıdaki optimizasyonlar kod tarafında otomatik olarak yapıldı:

1. ✅ **CloudWatch Log Seviyesi**: Sadece WARNING ve ERROR seviyesindeki loglar CloudWatch'a gönderiliyor (INFO ve DEBUG değil)
2. ✅ **S3 Cache Optimizasyonu**: Cache süresi 1 yıla çıkarıldı (CloudFront ile optimize)
3. ✅ **CloudWatch Log Retention**: Environment variable ile ayarlanabilir hale getirildi (varsayılan: 14 gün)

## 🔧 AWS Console'da Yapmanız Gerekenler

### 1. CloudWatch Log Retention Ayarlama (ÖNEMLİ - Hemen Yapın)

**Maliyet Etkisi**: Log saklama maliyeti %50-70 azalır

#### Adımlar:
1. AWS Console'a giriş yapın
2. **CloudWatch** → **Logs** → **Log groups** menüsüne gidin
3. `kuafora-backend` log group'unu bulun (yoksa oluşturun)
4. Log group'u seçin → **Actions** → **Edit retention**
5. **Retention period** seçin: **14 gün** (veya 30 gün)
6. **Save changes**

**Not**: Kod tarafında da retention ayarı var, ancak AWS Console'dan da ayarlamanız önerilir (daha güvenilir).

---

### 2. S3 Lifecycle Policy Oluşturma (ÖNEMLİ)

**Maliyet Etkisi**: Storage maliyeti %40-60 azalır

Eski media dosyalarını daha ucuz storage class'a taşıyın.

#### Adımlar:
1. AWS Console → **S3** → `kuafora-media` bucket'ını seçin
2. **Management** tab'ına gidin
3. **Lifecycle rules** → **Create lifecycle rule**
4. **Rule configuration**:
   - **Rule name**: `Move-old-files-to-IA`
   - **Rule scope**: **Apply to all objects in the bucket**
5. **Transitions**:
   - **Add transition**:
     - **Choose a transition**: **Move current versions of objects between storage classes**
     - **Days after object creation**: `30`
     - **Storage class**: **Standard-IA** (Infrequent Access)
   - **Add transition** (opsiyonel):
     - **Days after object creation**: `90`
     - **Storage class**: **Glacier Instant Retrieval** (veya **Glacier Flexible Retrieval** - daha ucuz ama daha yavaş)
6. **Expiration** (opsiyonel):
   - **Days after object creation**: `365` (1 yıl sonra sil)
7. **Create rule**

**Maliyet Karşılaştırması**:
- Standard: $0.023/GB/ay
- Standard-IA: $0.0125/GB/ay (%46 tasarruf)
- Glacier Instant Retrieval: $0.004/GB/ay (%83 tasarruf)

---

### 3. S3 Intelligent-Tiering (Opsiyonel - Otomatik Optimizasyon)

S3 otomatik olarak en uygun storage class'a taşır.

#### Adımlar:
1. S3 → `kuafora-media` bucket → **Management** → **Intelligent-Tiering**
2. **Create Intelligent-Tiering configuration**
3. **Configuration name**: `kuafora-intelligent-tiering`
4. **Scope**: **All objects in the bucket**
5. **Archive configurations**: 
   - ✅ **Enable Deep Archive Access** (en ucuz, nadiren erişilen dosyalar için)
6. **Create configuration**

**Not**: Intelligent-Tiering için aylık $0.0025/1000 object monitoring ücreti var, ancak storage tasarrufu genelde bunu karşılar.

---

### 4. Billing Alarm Oluşturma (ÖNEMLİ)

Aylık maliyet limitinizi aştığınızda uyarı alın.

#### Adımlar:
1. **CloudWatch** → **Alarms** → **Create alarm**
2. **Select metric**:
   - **Billing** → **EstimatedCharges** → **Total**
3. **Conditions**:
   - **Threshold type**: **Static**
   - **Whenever EstimatedCharges is**: **Greater than** → `50` (USD)
   - **Period**: **1 day**
4. **Notification**:
   - **Create new SNS topic** (ilk kez):
     - **Topic name**: `aws-billing-alerts`
     - **Email**: Kendi email adresiniz
     - **Create topic** → Email'inizi onaylayın
   - Veya mevcut bir SNS topic seçin
5. **Alarm name**: `Kuafora-Monthly-Billing-Alert`
6. **Create alarm**

**Önerilen Alarm Seviyeleri**:
- %80: `$40` (aylık $50 limit için)
- %100: `$50`
- %120: `$60`

---

### 5. Budget Oluşturma (Önerilen)

Daha detaylı maliyet takibi için.

#### Adımlar:
1. **Billing & Cost Management** → **Budgets** → **Create budget**
2. **Budget setup**:
   - **Budget type**: **Cost budget**
   - **Budget name**: `Kuafora-Monthly-Budget`
   - **Period**: **Monthly**
   - **Budget amount**: **Fixed** → `100` (USD)
3. **Configure alerts**:
   - **Alert 1**: %80 → `$80`
   - **Alert 2**: %100 → `$100`
   - **Alert 3**: %120 → `$120`
   - **Email recipients**: Kendi email adresiniz
4. **Create budget**

---

### 6. Cost Explorer'ı Aktifleştirme

Maliyet analizi için.

#### Adımlar:
1. **Billing & Cost Management** → **Cost Explorer**
2. İlk kez kullanıyorsanız: **Enable Cost Explorer** (24 saat sürebilir)
3. **Reports** → **Create report**:
   - **Report name**: `Kuafora-Monthly-Cost-Report`
   - **Time period**: **Last 30 days**
   - **Group by**: **Service** (S3, CloudWatch, EC2, etc.)
   - **Save report**

---

### 7. EC2 Instance Optimizasyonu (Opsiyonel)

#### A. Instance Type Kontrolü

1. **EC2** → **Instances** → Instance'ınızı seçin
2. **Instance type**'ı kontrol edin
3. Eğer CPU/Memory kullanımı düşükse, daha küçük instance type'a geçebilirsiniz:
   - **Actions** → **Instance settings** → **Change instance type**
   - Örnek: `t3.medium` → `t3.small` (%30-40 tasarruf)

**Not**: Instance'ı durdurmanız gerekebilir.

#### B. Reserved Instances (1 Yıllık Kullanım İçin)

Eğer instance'ınızı 1 yıl boyunca kullanacaksanız:

1. **EC2** → **Reserved Instances** → **Purchase Reserved Instances**
2. **Instance type**: Mevcut instance type'ınızı seçin
3. **Term**: **1 year**
4. **Payment option**: **All upfront** (en fazla indirim)
5. **Purchase**

**Maliyet Etkisi**: %30-40 indirim

---

### 8. CloudFront Cache Optimizasyonu

CloudFront kullanıyorsunuz (`d1uiu5mb5i1uph.cloudfront.net`). Cache ayarlarını optimize edin:

1. **CloudFront** → **Distributions** → Distribution'ınızı seçin
2. **Behaviors** tab'ına gidin
3. Default behavior'ı seçin → **Edit**
4. **Cache policy**: **CachingOptimized** (veya **CachingDisabled** + custom policy)
5. **TTL**: **86400** (1 gün) - static dosyalar için
6. **Save changes**

Bu, S3 request sayısını azaltır ve maliyeti düşürür.

---

## 📊 Beklenen Maliyet Tasarrufu

### Öncesi (Optimizasyon Öncesi):
- CloudWatch Logs: ~$15-30/ay
- S3 Storage: ~$10-20/ay
- EC2: Instance type'a göre
- **Toplam**: ~$30-60/ay

### Sonrası (Optimizasyon Sonrası):
- CloudWatch Logs: ~$5-10/ay (retention + log seviyesi filtresi)
- S3 Storage: ~$4-8/ay (lifecycle policy ile)
- EC2: Aynı veya %30-40 daha az (Reserved Instance ile)
- **Toplam**: ~$15-30/ay

**Tasarruf**: %40-60 azalma

---

## 🔍 Haftalık Kontrol Listesi

Her hafta şunları kontrol edin:

1. ✅ **Cost Explorer** → Son 7 günlük maliyet
2. ✅ **CloudWatch** → Billing alarm durumu
3. ✅ **S3** → Storage class dağılımı (Lifecycle policy çalışıyor mu?)
4. ✅ **CloudWatch Logs** → Log retention ayarları

---

## 🚨 Acil Durumlar

Eğer maliyet beklenmedik şekilde artarsa:

1. **Cost Explorer** → **Cost by service** → Hangi servis pahalı?
2. **CloudWatch Logs** → Log retention'ı kontrol edin (14 gün olmalı)
3. **S3** → Lifecycle policy çalışıyor mu?
4. **EC2** → Instance durumu ve kullanımı kontrol edin

---

## 📝 Notlar

- Kod tarafında yapılan optimizasyonlar otomatik olarak aktif
- AWS Console'daki ayarlar manuel yapılmalı
- İlk ay maliyetleri biraz yüksek olabilir (eski loglar ve dosyalar)
- İkinci aydan itibaren tasarruf belirginleşir

---

## 🆘 Yardım

Sorun yaşarsanız:
1. AWS Console → **Support** → **Support Center**
2. Cost Explorer'da detaylı analiz yapın
3. CloudWatch Logs'ta retention ayarını kontrol edin

---

**Son Güncelleme**: 2025-01-XX
**Optimizasyonlar Uygulandı**: ✅ Kod tarafı tamamlandı

