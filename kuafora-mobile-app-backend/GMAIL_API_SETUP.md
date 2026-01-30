# Gmail API ile E-posta Gönderimi

SMTP yerine **Google Gmail API** ile e-posta göndermek için aşağıdaki adımları uygulayın. Hem Gmail (@gmail.com) hem Google Workspace (info@kuafora.com) hesaplarıyla çalışır.

---

## 1. Google Cloud projesi ve OAuth2 kimlik bilgileri

1. [Google Cloud Console](https://console.cloud.google.com/) → **Proje oluştur** veya mevcut projeyi seçin.
2. **API’ler ve Hizmetler** → **Kütüphane** → **Gmail API** ara → **Etkinleştir**.
3. **API’ler ve Hizmetler** → **Kimlik Bilgileri** → **Kimlik Bilgisi Oluştur** → **OAuth istemci kimliği**.
4. Uygulama türü: **Masaüstü uygulaması** (veya **Web uygulaması**; yönlendirme URI’si gerekir).
5. Oluşturduktan sonra **İstemci ID** ve **İstemci gizli anahtarı**nı kopyalayın.

---

## 2. Refresh token almak (tek seferlik)

Gmail API, **OAuth2 refresh token** ile yetkilendirilir. Bu token’ı bir kez alıp `.env` içinde saklayacaksınız.

### Yöntem A: OAuth2 Playground (en pratik)

1. [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) sayfasına gidin.
2. Sağ üstte **dişli** simgesine tıklayın → **Use your own OAuth credentials** işaretleyin.
3. **OAuth Client ID** ve **OAuth Client secret** alanlarına Cloud Console’dan kopyaladığınız değerleri yapıştırın.
4. Soldaki listeden **Gmail API v1** altında **https://www.googleapis.com/auth/gmail.send** kapsamını işaretleyin.
5. **Authorize APIs** deyin; giriş yapın (info@kuafora.com veya kullanacağınız hesap).
6. **Exchange authorization code for tokens** deyin.
7. Sağ paneldeki **Refresh token** değerini kopyalayın (uzun bir metin). Bunu `.env` içinde `GMAIL_API_REFRESH_TOKEN` olarak kullanacaksınız.

### Yöntem B: Kendi script’iniz

Python ile OAuth2 akışı yapıp refresh token alabilirsiniz; `google-auth-oauthlib` kullanın ve kapsam olarak `https://www.googleapis.com/auth/gmail.send` verin. Elde ettiğiniz `credentials.refresh_token` değerini `.env`’e yazın.

---

## 3. Backend ortam değişkenleri

Backend kökündeki **`.env`** (veya production için `.env.prod`) dosyasına ekleyin:

```bash
# Gmail API (SMTP yerine Google API ile gönderim)
GMAIL_API_CLIENT_ID=xxxxxx.apps.googleusercontent.com
GMAIL_API_CLIENT_SECRET=GOCSPX-xxxxxx
GMAIL_API_REFRESH_TOKEN=1//0xxxxxx...

# Gönderen adresi (refresh token’ın sahibi hesap ile aynı olmalı)
DEFAULT_FROM_EMAIL=info@kuafora.com

# Şifre sıfırlama linki domain’i
PUBLIC_API_ORIGIN=https://api.kuafora.com
```

- **GMAIL_API_CLIENT_ID** / **GMAIL_API_CLIENT_SECRET**: Cloud Console’daki OAuth istemci kimlik bilgileri.
- **GMAIL_API_REFRESH_TOKEN**: OAuth2 Playground (veya script) ile aldığınız refresh token.
- **DEFAULT_FROM_EMAIL**: Maillerin “Kimden” adresi; refresh token’ın verdiğiniz hesap (örn. info@kuafora.com) ile aynı olmalı.

Bu üç Gmail API değişkeni tanımlı olduğunda backend otomatik olarak **Gmail API** backend’ini kullanır; SMTP ayarları (`EMAIL_HOST_USER` vb.) dikkate alınmaz.

---

## 4. Bağımlılıklar

```bash
pip install google-auth google-api-python-client
```

(Zaten `requirements.txt` içinde tanımlı.)

---

## 5. Şimdi ne yapmalı?

1. **Backend’i (yeniden) başlatın**  
   Örnek: `python manage.py runserver` veya production’da gunicorn/uwsgi restart. Böylece `.env` değerleri okunur.

2. **Hangi e-posta backend’inin kullanıldığını kontrol edin** (isteğe bağlı):
   ```bash
   python manage.py show_email_backend
   ```
   Gmail API kullanılıyorsa `GmailAPIEmailBackend` yazar.

3. **Test e-postası gönderin** veya uygulamadan **Kayıt ol** / **Şifremi unuttum** akışını deneyin.

---

## 6. Nasıl test edilir?

### A) Komut satırından tek mail

Kendinize veya bir adrese test maili gönderin (mevcut backend kullanılır — Gmail API ise Gmail üzerinden gider):

```bash
python manage.py sendtestemail your@email.com
```

Mail gelirse Gmail API (veya SMTP) çalışıyordur.

### B) Uygulama akışları

- **Kayıt ol:** Yeni e-posta ile kayıt → doğrulama kodu maili gelmeli.
- **Şifremi unuttum:** E-posta girip link talep et → sıfırlama linki maili gelmeli.

Mailler **DEFAULT_FROM_EMAIL** adresinden (örn. info@kuafora.com) Gmail API ile gidecektir.

### Hata durumunda

Loglarda `Gmail API send failed` veya `Gmail API service build failed` arayn. Genelde:
- Refresh token süresi dolmuş veya yanlış (OAuth Playground’dan yeniden alın).
- Scope eksik: `https://www.googleapis.com/auth/gmail.send` gerekli.

---

## 7. Kodlara nereden bakılır?

| Ne | Dosya |
|----|--------|
| Hangi backend kullanılıyor (Gmail / SMTP / console) | `config/settings.py` → `EMAIL_BACKEND`, `GMAIL_API_ENABLED` |
| Gmail API ile gönderim mantığı | `app/core/gmail_api_backend.py` |
| Mail gönderen yerler (kayıt, doğrulama, şifre sıfırlama) | `app/users/views.py` → `send_mail(...)` çağrıları |
| Günlük mail sayısı / uyarı | `app/users/email_tracking.py`, admin dashboard |

---

## Günlük limit

- **Gmail API** limitleri SMTP ile aynı hesap kotasına sayılır (Gmail: ~500/gün, Workspace: plana göre ~2000/gün).
- Kendi takibiniz: Admin paneli → **Dashboard** → **Günlük E-posta**; 400’ü geçince uyarı maili gider.
