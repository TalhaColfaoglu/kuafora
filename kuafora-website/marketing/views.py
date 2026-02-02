import json
import urllib.request
import urllib.error

from django.conf import settings
from django.shortcuts import render

try:
    from django.contrib.staticfiles.finders import find as static_find
except ImportError:
    def static_find(path):
        return None


def home(request):
    # Görsel yoksa veya manifest'te yoksa placeholder göster; {% static %} kullanılmadığı için 500 olmaz
    try:
        has_home_screen_image = static_find('img/screens/home-screen.png') is not None
    except Exception:
        has_home_screen_image = False
    return render(request, 'marketing/home.html', {'has_home_screen_image': has_home_screen_image})


def customer_app(request):
    return render(request, 'marketing/customer_app.html')

def support(request):
    return render(request, 'marketing/support.html')


def test_buttons(request):
    return render(request, 'test_buttons.html')


# Legal pages for main Kuafora app

def legal_terms(request):
    return render(request, 'marketing/legal_terms.html')


def legal_kvkk(request):
    return render(request, 'marketing/legal_kvkk.html')


def legal_cookies(request):
    return render(request, 'marketing/legal_cookies.html')


def legal_privacy(request):
    return render(request, 'marketing/legal_privacy.html')


def reset_password(request):
    """Şifre sıfırlama: GET form gösterir, POST API'ye iletir ve sonucu gösterir."""
    uid = (request.GET.get("uid") or request.POST.get("uid") or "").strip()
    token = (request.GET.get("token") or request.POST.get("token") or "").strip()
    error_message = None
    success = False

    if not uid or not token:
        error_message = "Eksik veya geçersiz bağlantı. E-postanızdaki linki kullanın veya uygulamadan yeni link isteyin."

    elif request.method == "POST":
        password1 = (request.POST.get("password1") or "").strip()
        password2 = (request.POST.get("password2") or "").strip()
        if not password1 or len(password1) < 8:
            error_message = "Şifre en az 8 karakter olmalıdır."
        elif password1 != password2:
            error_message = "İki şifre aynı olmalıdır."
        else:
            api_url = getattr(settings, "KUAFORA_API_URL", "https://api.kuafora.com").rstrip("/")
            reset_url = f"{api_url}/api/auth/reset-password/"
            data = json.dumps({"uid": uid, "token": token, "new_password": password1}).encode("utf-8")
            req = urllib.request.Request(
                reset_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if 200 <= resp.status < 300:
                        success = True
                    else:
                        error_message = "Şifre güncellenemedi. Link süresi dolmuş olabilir; yeni link isteyin."
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                try:
                    detail = json.loads(body).get("detail", "")
                    if "invalid" in (detail or "").lower():
                        error_message = "Link geçersiz veya süresi dolmuş. Şifremi unuttum ile yeni link alın."
                    else:
                        error_message = detail or "Şifre güncellenemedi."
                except Exception:
                    error_message = "Şifre güncellenemedi. Link süresi dolmuş olabilir."
            except Exception:
                error_message = "Bağlantı hatası. Lütfen tekrar deneyin."

    return render(
        request,
        "marketing/reset_password.html",
        {
            "uid": uid,
            "token": token,
            "error_message": error_message,
            "success": success,
        },
    )
