# Kuafora Web Sitesi — Görsel İhtiyaçları

Bu doküman, kuafora.com ve partner sayfalarında **nerede hangi görsellerin** kullanılacağını ve teknik beklentileri açıklar. Görsel temin ederken bu listeye göre hazırlamanız yeterlidir.

---

## 1. Ana sayfa (marketing/home.html)

### 1.1 Hero — Telefon mockup (ana ekran)
- **Dosya yolu (static):** `img/screens/home-screen.png`
- **Kullanım:** Hero bölümünde, sağ tarafta tek telefon mockup içinde gösterilen “Kuafora ana ekran” görseli.
- **Beklenti:** Müşteri uygulamasının ana ekranının ekran görüntüsü veya tasarım görseli (telefon çerçevesi template’e otomatik ekleniyor).
- **Önerilen boyut:** 1170×2532 px (veya 9:19.5 benzeri oran). Dikey, net, okunaklı.
- **Yoksa:** Şu an placeholder (gradient + “K” logosu + “Ana Ekran Görseli” metni) gösteriliyor.

### 1.2 Diğer hero / CTA bölümleri
- Şu an ek metin/bloklar için **ek görsel zorunluluğu yok**. İsterseniz:
  - “Keşfet” veya “Nasıl çalışır” bölümüne: harita veya uygulama keşif ekranı (opsiyonel).
  - “Üniversite öğrencileri” vurgusu için ayrı bir görsel talep edilmedi; metin ile veriliyor.

---

## 2. Müşteri uygulaması sayfası (marketing/customer_app.html)

- Sayfada **uygulama ekranları** veya **kullanım senaryosu** görselleri kullanılıyorsa:
  - **Öneri:** Müşteri uygulamasından 3–5 ekran: harita, salon listesi, salon detay, randevu, profil.
- **Dosya yolu önerisi:** `img/screens/customer-*.png` (örn. `customer-map.png`, `customer-salon-detail.png`).
- **Boyut:** 1170×2532 px veya aynı oran; tutarlılık için hepsi aynı çözünürlük.
- Şu an template’te bu sayfa için **zorunlu görsel alanı** yok; eklenirse bu path’ler kullanılabilir.

---

## 3. Partner sayfası (partner/partner_landing.html)

- **Tüm yönetim ve keşif sadece mobil uygulamada** vurgulandığı için görseller **telefon ekranı** odaklı olmalı.

### 3.1 Partner uygulaması — Takvim / bilgi yönetimi
- **Yer:** “İşletme bilgileri yönetimi” bölümü, sol/sağ phone mockup.
- **İçerik:** Partner uygulamasında takvim veya “işletme bilgileri” ekranı (hizmetler, saatler, personel).
- **Dosya yolu önerisi:** `img/screens/partner-calendar.png` veya `partner-info.png`.
- **Boyut:** 1170×2532 px (dikey).
- **Yoksa:** Şu an gri gradient + takvim ikonu + “Takvim” metni placeholder.

### 3.2 Partner uygulaması — Personel / hizmet yönetimi
- **Yer:** “Personel ve hizmet yönetimi” bölümü, phone mockup.
- **İçerik:** Personel listesi veya hizmet/kategori ekranı.
- **Dosya yolu önerisi:** `img/screens/partner-staff.png` veya `partner-services.png`.
- **Boyut:** 1170×2532 px.
- **Yoksa:** Placeholder (personel ikonu + “Personel” metni).

### 3.3 Partner uygulaması — İletişim / analiz
- **Yer:** “İletişim ve analiz” bölümü, phone mockup.
- **İçerik:** Chat/mesajlaşma ekranı veya basit istatistik ekranı.
- **Dosya yolu önerisi:** `img/screens/partner-chat.png` veya `partner-stats.png`.
- **Boyut:** 1170×2532 px.
- **Yoksa:** Placeholder (istatistik ikonu + “İstatistikler” metni).

### 3.4 Partner hero — Ana görsel
- **Yer:** Sayfa başındaki büyük phone mockup.
- **İçerik:** Partner uygulamasının ana ekranı veya dashboard benzeri bir ekran.
- **Dosya yolu önerisi:** `img/screens/partner-home.png`.
- **Yoksa:** “Partner Mobil Uygulaması” placeholder.

---

## 4. Genel / site çapında

### 4.1 Open Graph & Twitter Card
- **Dosya yolları (base.html):**
  - `img/og-image.jpg` — Sosyal medyada paylaşımda çıkan büyük görsel (önerilen: 1200×630 px).
  - `img/twitter-card.jpg` — Twitter kartı (önerilen: 1200×630 px veya aynı dosya).
- **İçerik:** Kuafora logosu + kısa slogan veya uygulama mockup’ı; okunaklı ve düşük boyutlu.

### 4.2 Favicon / ikonlar
- **Apple Touch Icon:** `img/apple-touch-icon.png` (180×180 px önerilir).
- Favicon şu an SVG (K logosu) ile veriliyor; ek PNG gerekmez.

---

## 5. Özet tablo

| Konum | Dosya (static/) | Açıklama | Önerilen boyut |
|-------|------------------|----------|-----------------|
| Ana sayfa hero | `img/screens/home-screen.png` | Müşteri uygulaması ana ekran | 1170×2532 px |
| Partner hero | `img/screens/partner-home.png` | Partner uygulaması ana ekran | 1170×2532 px |
| Partner — Takvim | `img/screens/partner-calendar.png` | Takvim / bilgi yönetimi ekranı | 1170×2532 px |
| Partner — Personel | `img/screens/partner-staff.png` | Personel / hizmet ekranı | 1170×2532 px |
| Partner — İstatistik | `img/screens/partner-stats.png` | Chat veya istatistik ekranı | 1170×2532 px |
| OG / Twitter | `img/og-image.jpg`, `img/twitter-card.jpg` | Paylaşım önizleme | 1200×630 px |
| Apple Touch | `img/apple-touch-icon.png` | Mobil bookmark ikonu | 180×180 px |

---

## 6. Görselleri nereye koyacaksınız?

- Proje kökünde `static/img/` altına:
  - `static/img/screens/` — uygulama ekran görselleri.
  - `static/img/og-image.jpg`, `static/img/twitter-card.jpg`, `static/img/apple-touch-icon.png`.
- Django’da `collectstatic` çalıştırıldığında bu dosyalar `staticfiles` (veya S3) içine alınır; şablonlar `{% static 'img/...' %}` ile kullanır.
- **home-screen.png** için şablon zaten `{% if 'img/screens/home-screen.png'|static_exists %}` ile kontrol ediyor: dosya yoksa placeholder gösteriliyor. Diğer ekranlar için de aynı mantık eklenebilir (path’ler yukarıdaki gibi).

Bu liste, mevcut şablon yapısına göre güncellenmiş durumdadır. Yeni bir bölüm veya sayfa eklendiğinde bu dokümana satır ekleyebilirsiniz.
