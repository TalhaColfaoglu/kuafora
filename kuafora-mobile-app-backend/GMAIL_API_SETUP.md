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

## 5. "invalid_grant: Bad Request" hatası

E-posta gönderirken **RefreshError: invalid_grant: Bad Request** alıyorsanız, sunucudaki **refresh token artık geçersiz** demektir.

**Neden olur?**
- Refresh token süresi dolmuş (uzun süre kullanılmadı, Google iptal etti).
- Hesap şifresi değişti veya “Güvenli olmayan uygulamalar” erişimi kapatıldı.
- OAuth istemci kimlik bilgileri (Client ID/Secret) yenilendi; eski refresh token yeni istemciyle çalışmaz.

**Ne yapmalı?**
1. **Yeni refresh token alın:** Yukarıdaki **2. Refresh token almak** adımını tekrarlayın (OAuth2 Playground ile giriş yapıp **Exchange authorization code for tokens** deyin).
2. Sunucudaki `.env` (veya `.env.prod`) içinde **GMAIL_API_REFRESH_TOKEN** değerini yeni token ile güncelleyin.
3. Backend’i yeniden başlatın (Docker ise container’ı restart edin).

---

## 5a. OAuth "Testing" modu — refresh token 7 gün sonra düşer (çok sık neden)

Google Cloud Console’da OAuth izin ekranı **"Testing"** (Test) modundaysa, **refresh token’lar yalnızca 7 gün geçerlidir**. 7 gün sonra "invalid_grant" alırsınız; yeni token alırsınız, yine 7 gün sonra düşer.

**Kalıcı çözüm (birini yapın):**

1. **Test kullanıcısı ekleyin (önerilen):**  
   [Google Cloud Console](https://console.cloud.google.com/) → **API’ler ve Hizmetler** → **OAuth izin ekranı** (OAuth consent screen).  
   Aşağı kaydırın → **Test kullanıcılar** (Test users) bölümü → **+ ADD USERS** → E-postaları **göndereceğiniz Gmail adresini** ekleyin (örn. `info@kuafora.com` veya kullandığınız hesap).  
   Bu hesapla OAuth2 Playground’dan aldığınız refresh token **7 gün sınırına takılmaz** (test kullanıcıları için token süresi düşmez).

2. **Veya uygulamayı yayınlayın:**  
   OAuth izin ekranında **"Uygulamayı yayınla"** (Publish app) deyin. Uygulama "Production" moduna geçer; refresh token süresi 7 gün ile sınırlı olmaz (Google’ın normal politikası geçerli olur).

Sunucuda tam hatayı görmek için:  
`python manage.py test_gmail_refresh`

---

## 5b. Yeni refresh token yazdım ama hâlâ invalid_grant

Yeni, güncel bir token yazıp kaydettiğiniz hâlde aynı hata devam ediyorsa genelde şunlardan biri vardır:

1. **Client ID / Client Secret uyuşmuyor**  
   Refresh token, onu üretirken kullandığınız OAuth istemcisine (Client ID + Secret) bağlıdır. Sunucudaki `GMAIL_API_CLIENT_ID` ve `GMAIL_API_CLIENT_SECRET` değerleri, OAuth2 Playground’da “Use your own OAuth credentials” ile girdiğiniz değerlerle **birebir aynı** olmalı. Farklı bir proje veya farklı bir “OAuth istemci kimliği” kullanıyorsanız token çalışmaz.

2. **Yanlış .env dosyası**  
   Backend, `DJANGO_ENV=production` ise **`.env.prod`**, değilse **`.env`** dosyasını okur. Docker’da production kullanıyorsanız token’ı **`.env.prod`** içine yazın veya `docker-compose` / ortam değişkenleriyle container’a verin. Sadece yerel `.env`’i güncellediyseniz sunucu/container hâlâ eski değeri görüyor olabilir.

3. **Container / process yeniden başlamadı**  
   `.env` veya `.env.prod` güncellense bile, process bir kez başladıktan sonra env’i bellekte tutar. Değişikliğin geçerli olması için backend’i (veya ilgili container’ı) **yeniden başlatın**:  
   `docker compose restart` veya ilgili servisi restart edin.

4. **Token kesilmiş veya bozulmuş**  
   Token tek satırda, başında/sonunda gereksiz boşluk veya satır sonu olmadan olmalı. Tırnak kullanıyorsanız sadece değerin kendisini tırnak içine alın; satır ortasında tırnak kırıp token’ı iki parçaya bölmeyin. Kopyalarken tamamının yapıştığından emin olun (özellikle uzun token’lar bazen kesilir).

5. **Scope uyuşmazlığı**  
   Token’ı alırken OAuth2 Playground’da **Gmail API v1 → https://www.googleapis.com/auth/gmail.send** kapsamı seçilmiş olmalı. Başka bir scope ile alınan token ile `gmail.send` çağrıları invalid_grant verebilir.

**Sunucuda ne okunduğunu kontrol etmek için** (token’ın kendisi yazdırılmaz, sadece uzunluk ve maskeli önizleme):

```bash
python manage.py check_gmail_token
```

Bu komut hangi env dosyasının okunduğunu, token uzunluğunu ve CLIENT_ID/CLIENT_SECRET’ın dolu olup olmadığını gösterir. Token uzunluğu 50’den kısa çıkıyorsa büyük ihtimalle kesilmiş veya yanlış yapışmıştır.

---

## 6. Şimdi ne yapmalı?

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

Mail gelirse Gmail API çalışıyordur.

### B) Uygulama akışları

- **Kayıt ol:** Yeni e-posta ile kayıt → doğrulama kodu maili gelmeli.
- **Şifremi unuttum:** E-posta girip link talep et → sıfırlama linki maili gelmeli.

Mailler **DEFAULT_FROM_EMAIL** adresinden (örn. info@kuafora.com) Gmail API ile gidecektir.

### Hata durumunda

Loglarda `Gmail API send failed` veya `Gmail API service build failed` arayn. Genelde:
- Refresh token süresi dolmuş veya yanlış (OAuth Playground’dan yeniden alın).
- Scope eksik: `https://www.googleapis.com/auth/gmail.send` gerekli.

#### `invalid_grant: Bad Request` / `RefreshError`

Bu hata **refresh token'ın geçersiz veya süresi dolmuş** olduğu anlamına gelir. Yapmanız gerekenler:

1. **[OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)** sayfasına gidin.
2. Dişli → **Use your own OAuth credentials** işaretleyin; mevcut `GMAIL_API_CLIENT_ID` ve `GMAIL_API_CLIENT_SECRET` değerlerinizi girin.
3. **Gmail API v1** → **https://www.googleapis.com/auth/gmail.send** kapsamını seçin.
4. **Authorize APIs** → giriş yapın (mail gönderecek hesap).
5. **Exchange authorization code for tokens** → sağdaki **Refresh token** değerini kopyalayın.
6. Sunucudaki `.env` (veya container env) içinde `GMAIL_API_REFRESH_TOKEN` değerini bu yeni token ile güncelleyin.
7. Backend'i yeniden başlatın (`docker compose restart backend_dev` veya gunicorn restart).

Not: Google hesap şifresi değiştiyse veya "güvenli olmayan uygulama erişimi" kapatıldıysa refresh token iptal olur; yukarıdaki adımlarla yeniden almanız gerekir.

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
