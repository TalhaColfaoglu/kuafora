# Güvenlik Rehberi

Bu doküman, Kuafora uygulamasının güvenlik önlemlerini ve yapılması gerekenleri açıklar.

## ✅ Uygulanan Güvenlik Önlemleri

### 1. Veri Şifreleme
- **Telefon Numaraları**: Fernet encryption ile şifreleniyor
- **Şifreler**: Django'nun PBKDF2 hash algoritması ile hash'leniyor
- **API Key'ler**: Environment variables'da saklanıyor

### 2. Authentication & Authorization
- JWT token tabanlı authentication
- Token refresh mekanizması
- Token blacklist desteği
- Email verification zorunluluğu
- Secure cookie settings (HTTPOnly, Secure, SameSite)

### 3. Rate Limiting
- Login: 5/dakika
- Register: 3/dakika
- Email check: 10/dakika
- Password reset: 3/dakika
- Genel API: 1000/saat

### 4. Security Headers (Production)
- HSTS (HTTP Strict Transport Security)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection
- Secure Referrer Policy
- Content Security Policy (CSP)
- Permissions Policy

### 5. Input Validation
- Django form validation
- DRF serializer validation
- Password strength requirements (min 8 karakter, complexity rules)
- SQL injection pattern detection
- XSS pattern detection
- File upload validation (extension, size)

### 6. CORS & CSRF Protection
- CORS whitelist yapılandırması
- CSRF token koruması
- Secure cookie ayarları
- Custom CSRF failure handler

### 7. Error Handling
- Generic error messages (information disclosure önleme)
- Sensitive data sanitization
- Custom exception handler

### 8. Request Security
- Request size limiting (10MB max)
- Query timeout (30 seconds)
- File upload size limits
- Field count limits

### 9. Audit Logging
- Authentication attempt logging
- Failed login tracking
- Security event monitoring

### 10. Session Security
- Secure session cookies
- HTTPOnly cookies
- SameSite protection
- Session timeout configuration

### 11. Database Security
- Connection timeout
- Query timeout
- Connection pooling
- Optional admin IP whitelist

## 🔒 Yapılması Gerekenler

### 1. Environment Variables Güvenliği

**Production sunucusunda:**

```bash
# 1. .env dosyalarının izinlerini kontrol edin
chmod 600 kuafora-mobile-app-backend/.env.prod
chmod 600 kuafora/env/backend.env

# 2. .env dosyalarının git'e eklenmediğinden emin olun
git check-ignore kuafora-mobile-app-backend/.env.prod
git check-ignore kuafora/env/backend.env

# 3. Production'da SECRET_KEY'i güçlü bir değerle değiştirin
# Python ile güçlü key oluşturun:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. PHONE_ENCRYPTION_KEY'i oluşturun:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Database Güvenliği

```bash
# 1. PostgreSQL kullanıcı şifresini güçlü yapın
# 2. Database'e sadece uygulama sunucusundan erişilebilir olduğundan emin olun
# 3. Regular backup alın ve backup'ları şifreleyin
```

### 3. Server Güvenliği

```bash
# 1. Firewall kuralları:
#    - Sadece gerekli portları açın (80, 443, SSH)
#    - Database portunu (5432) sadece internal network'ten erişilebilir yapın

# 2. SSH güvenliği:
#    - Password authentication'ı kapatın, key-based auth kullanın
#    - Root login'i kapatın
#    - Fail2ban kurun

# 3. SSL/TLS sertifikaları:
#    - Let's Encrypt ile ücretsiz sertifika alın
#    - Sertifikaları düzenli yenileyin (otomatik)
```

### 4. Monitoring & Logging

```bash
# 1. Log dosyalarını düzenli rotate edin
# 2. Log'larda sensitive data olmadığından emin olun
# 3. Failed login attempt'leri monitor edin
# 4. Rate limit violation'ları takip edin
```

### 5. Code Security

```bash
# 1. Düzenli dependency update:
pip list --outdated
pip install --upgrade <package>

# 2. Security vulnerability taraması:
pip install safety
safety check

# 3. Code review yaparken:
#    - Hardcoded credentials kontrolü
#    - SQL injection riski
#    - XSS riski
#    - CSRF koruması
```

### 6. API Security Checklist

- [ ] Tüm endpoint'lerde authentication kontrolü
- [ ] Sensitive data'nın response'larda expose edilmemesi
- [ ] Input validation her yerde
- [ ] Rate limiting aktif
- [ ] Error message'lar generic
- [ ] Logging'de sensitive data yok

### 7. Frontend Security

- [ ] FlutterSecureStorage kullanımı (✅ yapıldı)
- [ ] HTTPS zorunluluğu production'da
- [ ] Token'lar secure storage'da saklanıyor (✅ yapıldı)
- [ ] API key'ler hardcoded değil

## 🚨 Acil Güvenlik Kontrol Listesi

Production'a deploy etmeden önce:

1. ✅ SECRET_KEY güçlü ve unique
2. ✅ PHONE_ENCRYPTION_KEY set edilmiş
3. ✅ Database password güçlü
4. ✅ DEBUG=False production'da
5. ✅ ALLOWED_HOSTS doğru yapılandırılmış
6. ✅ HTTPS aktif
7. ✅ Security headers aktif
8. ✅ Rate limiting aktif
9. ✅ CORS whitelist doğru
10. ✅ .env dosyaları git'e eklenmemiş

## 📞 Güvenlik İhlali Durumunda

1. **Hemen tüm token'ları invalidate edin:**
   ```python
   python manage.py shell
   from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
   OutstandingToken.objects.all().delete()
   ```

2. **Kullanıcı şifrelerini reset edin** (gerekirse)

3. **Log'ları inceleyin** ve ihlalin kaynağını bulun

4. **Güvenlik açığını kapatın**

5. **Kullanıcıları bilgilendirin** (gerekirse)

## 🔐 Best Practices

1. **Principle of Least Privilege**: Her kullanıcı/kod sadece gerekli yetkilere sahip olmalı
2. **Defense in Depth**: Birden fazla güvenlik katmanı
3. **Fail Secure**: Hata durumunda güvenli moda geç
4. **Security by Design**: Güvenlik baştan tasarıma dahil edilmeli
5. **Regular Updates**: Düzenli güvenlik güncellemeleri

## 🔐 Ek Güvenlik Önlemleri (Yeni Eklenenler)

### 1. Request Size Limiting
- Maksimum 10MB request boyutu
- DoS saldırılarını önler

### 2. Security Headers Middleware
- Content Security Policy (CSP)
- Permissions Policy
- Server bilgisi gizleme

### 3. Audit Logging
- Authentication attempt'leri loglanıyor
- Failed login tracking
- Security event monitoring

### 4. Input Validation
- SQL injection pattern detection
- XSS pattern detection
- File upload validation (extension, size, filename sanitization)

### 5. Session & CSRF Security
- Secure cookies (HTTPS only in production)
- HTTPOnly cookies
- SameSite protection
- Custom CSRF failure handler

### 6. Database Security
- Connection timeout (10 seconds)
- Query timeout (30 seconds)
- Connection pooling (10 minutes)

### 7. File Upload Security
- Extension whitelist
- Size limits (10MB)
- Filename sanitization

### 8. IP Whitelist (Optional)
- Admin panel için IP whitelist desteği
- Environment variable ile kontrol edilebilir

## 📚 Kaynaklar

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Django Security](https://docs.djangoproject.com/en/stable/topics/security/)
- [Flutter Security](https://docs.flutter.dev/security)

