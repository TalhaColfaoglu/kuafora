import json
import urllib.request
import urllib.error
import urllib.parse

from django.conf import settings
from django.http import Http404
from django.shortcuts import render

try:
    from django.contrib.staticfiles.finders import find as static_find
except ImportError:
    def static_find(path):
        return None


SALON_THEME_PRESETS = {
    "forest": {
        "accent": "#2D6A4F",
        "accent_soft": "#E8F4EE",
        "page_bg": "#F6F8F6",
        "surface": "#FFFFFF",
        "text": "#142018",
        "muted": "#5F6F65",
        "border": "#DCE5DE",
    },
    "charcoal": {
        "accent": "#1F2937",
        "accent_soft": "#EEF2F7",
        "page_bg": "#F6F7F9",
        "surface": "#FFFFFF",
        "text": "#111827",
        "muted": "#6B7280",
        "border": "#E5E7EB",
    },
    "sand": {
        "accent": "#B7791F",
        "accent_soft": "#FFF7E8",
        "page_bg": "#FBF8F1",
        "surface": "#FFFFFF",
        "text": "#2F2419",
        "muted": "#7B6B58",
        "border": "#EADFCF",
    },
    "burgundy": {
        "accent": "#8D2B4F",
        "accent_soft": "#FCEEF3",
        "page_bg": "#FBF6F8",
        "surface": "#FFFFFF",
        "text": "#2B1220",
        "muted": "#7E5A68",
        "border": "#E9D8DF",
    },
    "midnight": {
        "accent": "#214E87",
        "accent_soft": "#EDF4FF",
        "page_bg": "#F5F8FC",
        "surface": "#FFFFFF",
        "text": "#122033",
        "muted": "#627089",
        "border": "#D8E1EC",
    },
}

SALON_FONT_STACKS = {
    "cabinet": "\"Cabinet Grotesk\", \"Inter\", system-ui, sans-serif",
    "playfair": "\"Playfair Display\", Georgia, serif",
    "manrope": "\"Manrope\", \"Inter\", system-ui, sans-serif",
    "sora": "\"Sora\", \"Inter\", system-ui, sans-serif",
    "satoshi": "\"Satoshi\", \"Inter\", system-ui, sans-serif",
    "inter": "\"Inter\", system-ui, sans-serif",
    "dm_sans": "\"DM Sans\", \"Inter\", system-ui, sans-serif",
}


def _fetch_api_json(path: str, params: dict | None = None, timeout: int = 15):
    api_url = getattr(settings, "KUAFORA_API_URL", "https://api.kuafora.com").rstrip("/")
    full_url = f"{api_url}/api/{path.lstrip('/')}"
    if params:
        clean_params = {k: v for k, v in params.items() if v not in (None, "", [])}
        if clean_params:
            full_url = f"{full_url}?{urllib.parse.urlencode(clean_params)}"
    request = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except Exception:
        return None


def _salon_theme_context(shop: dict) -> dict:
    web_settings = shop.get("web_settings") or {}
    theme_key = (web_settings.get("theme_color") or "forest").strip().lower()
    heading_font_key = (web_settings.get("heading_font") or "cabinet").strip().lower()
    body_font_key = (web_settings.get("body_font") or "satoshi").strip().lower()
    return {
        "theme": SALON_THEME_PRESETS.get(theme_key, SALON_THEME_PRESETS["forest"]),
        "heading_font_css": SALON_FONT_STACKS.get(heading_font_key, SALON_FONT_STACKS["cabinet"]),
        "body_font_css": SALON_FONT_STACKS.get(body_font_key, SALON_FONT_STACKS["satoshi"]),
    }


def _maptiler_static_url(lat, lng) -> str | None:
    key = (getattr(settings, "MAPTILER_API_KEY", "") or "").strip()
    if not key or lat is None or lng is None:
        return None
    return f"https://api.maptiler.com/maps/streets/static/{lng},{lat},14/1200x520.png?key={key}"


def _osm_embed_url(lat: float, lng: float, delta: float = 0.008) -> str:
    """OpenStreetMap embed iframe URL (MapTiler yoksa fallback)."""
    min_lat, max_lat = lat - delta, lat + delta
    min_lng, max_lng = lng - delta, lng + delta
    bbox = f"{min_lng},{min_lat},{max_lng},{max_lat}"
    return f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik&marker={lat},{lng}"


def _normalize_google_maps_url(raw: str | None) -> str | None:
    """Google Maps linkini tıklanabilir URL'ye çevirir."""
    if not raw or not (s := str(raw).strip()):
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return f"https://{s}"


def _normalize_instagram_url(raw: str | None) -> str | None:
    """Instagram username veya URL'yi tam linke çevirir."""
    if not raw or not (s := str(raw).strip()):
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    username = s.lstrip("@").split("/")[-1].split("?")[0]
    if not username:
        return None
    return f"https://instagram.com/{username}"


def _normalize_facebook_url(raw: str | None) -> str | None:
    """Facebook username/page veya URL'yi tam linke çevirir."""
    if not raw or not (s := str(raw).strip()):
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if "facebook.com" in s or "fb.com" in s or "fb.me" in s:
        return s if s.startswith("http") else f"https://{s}"
    page = s.lstrip("/").split("/")[0].split("?")[0]
    if not page:
        return None
    return f"https://facebook.com/{page}"


def _normalize_twitter_url(raw: str | None) -> str | None:
    """Twitter/X username veya URL'yi tam linke çevirir."""
    if not raw or not (s := str(raw).strip()):
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    username = s.lstrip("@").split("/")[-1].split("?")[0]
    if not username:
        return None
    return f"https://x.com/{username}"


def _normalize_whatsapp_url(raw: str | None) -> str | None:
    """WhatsApp numarasını wa.me linkine çevirir."""
    if not raw or not (s := str(raw).strip()):
        return None
    if s.startswith("http://") or s.startswith("https://"):
        return s
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return None
    if digits.startswith("0") and len(digits) == 11:
        digits = "9" + digits
    elif not digits.startswith("90") and len(digits) <= 10:
        digits = "90" + digits.lstrip("0")
    return f"https://wa.me/{digits}"


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


def salons(request):
    q = (request.GET.get("q") or "").strip()
    city = (request.GET.get("city") or "").strip()
    district = (request.GET.get("district") or "").strip()
    page = (request.GET.get("page") or "1").strip()
    try:
        page_number = max(1, int(page))
    except ValueError:
        page_number = 1

    filters = _fetch_api_json("barbershops/available-locations/") or {}
    listing = _fetch_api_json(
        "barbershops/",
        {
            "q": q,
            "city": city,
            "district": district,
            "page": page_number,
        },
    ) or {}

    if isinstance(listing, dict) and "results" in listing:
        salons_list = listing.get("results") or []
        count = listing.get("count") or 0
        next_url = listing.get("next")
        prev_url = listing.get("previous")
    elif isinstance(listing, list):
        salons_list = listing
        count = len(salons_list)
        next_url = None
        prev_url = None
    else:
        salons_list = []
        count = 0
        next_url = None
        prev_url = None

    selected_city_districts = []
    if isinstance(filters, dict) and city:
        selected_city_districts = filters.get(city, []) or []

    return render(
        request,
        "marketing/salons_list.html",
        {
            "salons": salons_list,
            "salon_count": count,
            "available_locations": filters if isinstance(filters, dict) else {},
            "selected_city_districts": selected_city_districts,
            "selected_city": city,
            "selected_district": district,
            "search_query": q,
            "page_number": page_number,
            "next_url": next_url,
            "prev_url": prev_url,
        },
    )


def salon_detail(request, slug):
    payload = _fetch_api_json(f"barbershops/website/{slug}/")
    if not isinstance(payload, dict):
        raise Http404("Salon bulunamadı")

    shop = payload.get("shop") or {}
    if not shop:
        raise Http404("Salon bulunamadı")

    lat = shop.get("latitude")
    lng = shop.get("longitude")
    try:
        lat = float(lat) if lat is not None else None
        lng = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        lat = None
        lng = None

    theme_context = _salon_theme_context(shop)
    og_image = shop.get("main_image") or shop.get("main_image_thumb")
    description = (shop.get("description") or "").strip()
    fallback_description = f"{shop.get('name', 'Kuafora salonu')} - {shop.get('district', '')} {shop.get('city', '')}".strip()

    google_maps_url = _normalize_google_maps_url(shop.get("google_maps_link"))
    if not google_maps_url and lat is not None and lng is not None:
        google_maps_url = f"https://www.google.com/maps?q={lat},{lng}"

    shop_links = {
        "google_maps": google_maps_url,
        "instagram": _normalize_instagram_url(shop.get("instagram")),
        "facebook": _normalize_facebook_url(shop.get("facebook")),
        "twitter": _normalize_twitter_url(shop.get("twitter")),
        "whatsapp": _normalize_whatsapp_url(shop.get("whatsapp")),
    }

    return render(
        request,
        "marketing/salon_detail.html",
        {
            "payload": payload,
            "shop": shop,
            "shop_links": shop_links,
            "working_hours": payload.get("working_hours") or [],
            "services_grouped": payload.get("services_grouped") or [],
            "staff_list": payload.get("staff") or [],
            "feature_labels": payload.get("feature_labels") or [],
            "theme": theme_context["theme"],
            "heading_font_css": theme_context["heading_font_css"],
            "body_font_css": theme_context["body_font_css"],
            "maptiler_key": (getattr(settings, "MAPTILER_API_KEY", "") or "").strip(),
            "maptiler_static_url": _maptiler_static_url(lat, lng),
            "osm_embed_url": _osm_embed_url(lat, lng) if lat is not None and lng is not None else None,
            "lat": lat,
            "lng": lng,
            "page_description": description or fallback_description,
            "og_image": og_image,
        },
    )


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
