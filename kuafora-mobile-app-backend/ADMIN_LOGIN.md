# Admin Paneline Giriş

Admin paneline giriş yapamıyorsanız aşağıdakileri kontrol edin.

## 1. Kullanıcının admin yetkisi olmalı

Django admin panele **sadece `is_staff=True`** olan kullanıcılar girebilir. Normal kayıtla oluşan hesaplar `is_staff=False` olduğu için giriş yapamaz.

### Seçenek A: Yeni superuser oluştur

```bash
# Sunucuda (Docker kullanıyorsanız)
docker compose exec backend_dev python manage.py createsuperuser
```

E-posta ve şifre girin (bu projede giriş e-posta ile yapılır).

### Seçenek B: Mevcut kullanıcıyı admin yap

Zaten kayıtlı bir e-postayı admin yapmak için:

```bash
docker compose exec backend_dev python manage.py make_staff kullanici@email.com
```

Bu komut ilgili kullanıcıya `is_staff=True` ve `is_superuser=True` atar. Ardından **admin giriş sayfasında bu e-posta ve mevcut şifre** ile giriş yapabilirsiniz.

## 2. IP kısıtlaması (ADMIN_IP_WHITELIST)

`backend.dev.env` içinde `ADMIN_IP_WHITELIST` tanımlıysa, sadece bu listedeki IP’ler admin sayfalarına erişebilir. Erişim 403 alıyorsanız:

- Kendi IP’nizi listeye ekleyin, **veya**
- Geliştirme ortamında bu değişkeni **boş bırakın** (tüm IP’lere izin verir).

## 3. Giriş bilgileri

- **URL:** `https://api-dev.kuafora.com/admin/` (veya sunucudaki admin adresi)
- **Kullanıcı:** E-posta adresi (kullanıcı adı değil)
- **Şifre:** Hesabın şifresi

Giriş sonrası 200 alıp yine login sayfasına dönüyorsanız büyük ihtimalle kullanıcı staff değildir; **Seçenek B** ile `make_staff` çalıştırın.
