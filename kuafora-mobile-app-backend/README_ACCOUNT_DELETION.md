# Hesap Silme (Kullanıcı Kendi Hesabını Silme)

Bu doküman, **admin panelinde kullanıcı silme** ve **mobil/web uygulamalarında kullanıcının kendi hesabını ayarlar üzerinden silmesi** ile ilgilidir.

---

## 1. Admin panelinde kullanıcı silme

- **Durum:** Süper kullanıcı veya `users.delete_user` yetkisi olan personel, Django admin → Kullanıcılar listesinden tek bir kullanıcıyı silebilir (Sil butonu ve "Seçilen kullanıcıları sil" aksiyonu).
- **Yetki:** `UserAdmin.has_delete_permission` sadece `is_superuser` veya `users.delete_user` izni olanlara `True` döner.

---

## 2. Kullanıcının kendi hesabını silmesi (API)

Kullanıcı giriş yapmışken kendi hesabını kalıcı olarak silebilir.

### Endpoint

- **URL:** `POST` veya `DELETE` → `/api/auth/delete-account/`
- **Kimlik doğrulama:** Gerekli (Bearer JWT veya session).
- **İstek gövdesi:** Boş (body yok).

### Örnek (curl)

```bash
curl -X POST "https://api.example.com/api/auth/delete-account/" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json"
```

### Başarılı yanıt (200 OK)

```json
{
  "detail": "Hesabınız kalıcı olarak silindi."
}
```

### Hata yanıtları

- **401:** Giriş yapılmamış.
- **400:** İlişkili veriler nedeniyle silme yapılamıyor (örn. bekleyen işlemler); kullanıcıya destek ile iletişime geçmesi önerilir.
- **500:** Sunucu hatası; yine destek ile iletişim önerilir.

---

## 3. Her iki uygulamada (müşteri + kuaför) ayarlarda hesap silme

İstek: Kullanıcılar **ayarlar** ekranında, çok göze batmayan bir bölümde kendi hesaplarını silebilsin.

### Önerilen UI

- **Konum:** Ayarlar sayfasının **en altında**, ayrı bir bölüm olarak (örn. "Hesap" veya "Güvenlik ve hesap").
- **Metin önerisi:** "Hesabımı kalıcı olarak sil" veya "Hesabı kapat" gibi net ama tek satırlık bir link/buton.
- **Onay:** Tek tıkla silme yapmayın; en az bir onay diyaloğu gösterin: "Hesabınız ve tüm verileriniz kalıcı olarak silinecek. Bu işlem geri alınamaz. Emin misiniz?" ve "Evet, sil" / "Vazgeç" seçenekleri.
- **Görünürlük:** Dikkat çekici bir uyarı rengi (kırmızı/gri) kullanılabilir ama ana aksiyonların yanında abartılı olmayacak şekilde; sadece ayarların altında küçük bir satır da yeterli.

### Teknik (mobil / web)

1. Kullanıcı giriş yapmış olmalı; isteklerde mevcut **JWT** (veya session) kullanılmalı.
2. Onay sonrası:
   - `POST` veya `DELETE` → `BASE_URL/api/auth/delete-account/`
   - Header: `Authorization: Bearer <access_token>`
3. 200 dönerse: yerel oturumu temizleyin (token kaldır, çıkış yap) ve kullanıcıyı giriş/onboarding ekranına yönlendirin.
4. 4xx/5xx dönerse: Sunucudan gelen `detail` mesajını kullanıcıya gösterin (ve gerekirse "Destek ile iletişime geçin" notu ekleyin).

### Base URL

- Geliştirme: `http://localhost:8000` (veya projenizin API adresi).
- Canlı: `https://api.kuafora.com` (veya kullandığınız API domain’i).

---

## Özet

| Konu | Açıklama |
|------|----------|
| Admin silme | Süper kullanıcı veya `users.delete_user` yetkisi ile çalışır. |
| Kendi hesabını silme API | `POST` veya `DELETE` → `/api/auth/delete-account/`, yetkili istek. |
| Uygulama tarafı | Her iki uygulamada (müşteri + kuaför) Ayarlar’da, altta ve onaylı "Hesabı sil" seçeneği eklenmeli. |

Mobil (Flutter) veya web projesinde Ayarlar ekranına bu çağrıyı ve onay akışını eklemeniz yeterlidir; backend tarafı hazırdır.
