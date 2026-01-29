# E-posta (Gmail SMTP) Kurulumu

Bu projede **ilk kayıt e-posta doğrulama** ve **şifremi unuttum** akışları e-posta ile çalışır. Gmail SMTP kullanıyorsanız aşağıdaki adımları uygulayın.

---

## 1. Gmail’de 2 Adımlı Doğrulama (2FA) Açın

1. [Google Hesabı](https://myaccount.google.com/) → **Güvenlik**
2. **2 Adımlı Doğrulama** bölümünde **Başlay** deyin ve adımları tamamlayın.
3. Bu adım zorunludur; Gmail “Uygulama şifresi” ancak 2FA açıkken oluşturulur.

---

## 2. Uygulama Şifresi (App Password) Oluşturun

1. [Google Hesabı](https://myaccount.google.com/) → **Güvenlik**
2. **2 Adımlı Doğrulama** açık olmalı. Aşağı kaydırın.
3. **Uygulama şifreleri** bölümüne girin.
4. **Uygulama seçin** → **Posta** (veya “Diğer” yazıp örn. “Kuafora”)
5. **Cihaz seçin** → **Diğer** → “Kuafora Backend” gibi bir isim verin.
6. **Oluştur** deyin; 16 karakterlik bir şifre (boşluksuz) gösterilir.
7. Bu şifreyi kopyalayın; **sadece bir kez** gösterilir. `.env` dosyasına yapıştıracaksınız.

---

## 3. Ortam Değişkenlerini Ayarlayın

Backend projesinin kökündeki **`.env`** (veya production için `.env.prod`) dosyasına şunları ekleyin:

```bash
# Gmail SMTP (e-posta doğrulama + şifremi unuttum)
EMAIL_HOST_USER=your.gmail@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
```

- **EMAIL_HOST_USER**: E-postaların gönderileceği Gmail adresi (yukarıda 2FA açtığınız hesap).
- **EMAIL_HOST_PASSWORD**: Az önce oluşturduğunuz 16 karakterlik uygulama şifresi (aralıklı veya aralıksız yazılabilir; Django boşlukları yok sayar).

İsteğe bağlı:

```bash
# Varsayılan: smtp.gmail.com ve 587 kullanılır
# Farklı SMTP kullanıyorsanız:
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=1

# Gönderen adresi (boş bırakırsanız EMAIL_HOST_USER kullanılır)
# DEFAULT_FROM_EMAIL=your.gmail@gmail.com

# Şifre sıfırlama linkinin domain’i (mobil uygulama web sayfası için)
PUBLIC_API_ORIGIN=https://api.kuafora.com
```

---

## 4. Test Etme

1. Backend’i yeniden başlatın (env değişkenleri yüklensin).
2. **Kayıt ol**: Yeni bir e-posta ile kayıt olun; e-posta kutusuna doğrulama kodu gelmeli.
3. **Şifremi unuttum**: Giriş ekranında “Şifremi unuttum” deyip e-posta girin; sıfırlama linki gelmeli.

E-posta gelmiyorsa:

- **Spam / Gereksiz** klasörünü kontrol edin.
- `.env` içinde `EMAIL_HOST_USER` ve `EMAIL_HOST_PASSWORD` doğru mu kontrol edin.
- Backend loglarında `[EMAIL][RESET]` veya `[EMAIL][VERIFY_CODE]` hata mesajı var mı bakın.

---

## 5. Akış Özeti

| Özellik | Davranış |
|--------|----------|
| **İlk kayıt** | Kayıt sonrası e-posta doğrulama kodu gönderilir. Doğrulama yapılmadan giriş yapılamaz. |
| **Giriş** | E-posta doğrulanmamış hesap ile giriş engellenir; “E-posta doğrulaması gerekli” mesajı döner. |
| **Şifremi unuttum** | Girilen e-posta kayıtlıysa şifre sıfırlama linki e-posta ile gönderilir. |

SMTP ayarlanmazsa (geliştirme ortamında): DEBUG modunda e-postalar **konsola** yazılır; production’da mail gönderilmez (dummy backend).
