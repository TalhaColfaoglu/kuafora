from django_filters import rest_framework as filters
from django.utils import timezone
from django.db.models import Q, F, Value
from django.db.models.functions import Lower, Replace
from .models import Barbershop, ShopCategory


def _normalize_tr(s: str) -> str:
    """Türkçe/Latince ve büyük/küçük harf duyarsız arama için metni normalize et."""
    s = (s or "").strip().lower()
    # Türkçe büyük İ (U+0130) Python default locale'de .lower() ile 'i' olmayabilir; açıkça dönüştür
    s = s.replace("\u0130", "i").replace("İ", "i")
    s = (
        s.replace("ı", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    s = " ".join(s.split())
    return s


def _norm_db_expr(field_name: str):
    """Veritabanı alanını arama için normalize eden annotate ifadesi (büyük/küçük harf + Türkçe/Latin)."""
    # Önce Türkçe büyük İ'yi dönüştür (Lower bazı locale'lerde İ'yi farklı işleyebilir)
    expr = Replace(F(field_name), Value("İ"), Value("i"))
    expr = Lower(expr)
    expr = Replace(expr, Value("ı"), Value("i"))
    expr = Replace(expr, Value("ş"), Value("s"))
    expr = Replace(expr, Value("ğ"), Value("g"))
    expr = Replace(expr, Value("ü"), Value("u"))
    expr = Replace(expr, Value("ö"), Value("o"))
    expr = Replace(expr, Value("ç"), Value("c"))
    return expr


class BarbershopFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_q")
    city = filters.CharFilter(method="filter_city")
    district = filters.CharFilter(method="filter_district")
    gender = filters.CharFilter(method="filter_gender")
    categories = filters.ModelMultipleChoiceFilter(
        field_name="categories",
        queryset=ShopCategory.objects.all(),
    )
    is_open = filters.BooleanFilter(method="filter_is_open")

    class Meta:
        model = Barbershop
        fields = ("q", "city", "district", "gender", "categories", "is_open")

    def filter_q(self, queryset, name, value):
        """
        Robust search:
        - İl/ilçe, büyük/küçük harf, Latince/Türkçe karakter duyarsız
        - Turkish character tolerant: i/ı, İ, s/ş, g/ğ, u/ü, o/ö, c/ç
        - Tokenized search across: name, city, district, category name, service name
        """
        raw = (value or "").strip()
        if not raw:
            return queryset

        q_norm = _normalize_tr(raw)
        tokens = [t for t in q_norm.split(" ") if t]
        if not tokens:
            return queryset

        qs = queryset.annotate(
            _n_name=_norm_db_expr("name"),
            _n_city=_norm_db_expr("city"),
            _n_district=_norm_db_expr("district"),
            _n_category=_norm_db_expr("categories__name"),
            _n_service=_norm_db_expr("services__name"),
        )

        for t in tokens:
            qs = qs.filter(
                Q(_n_name__contains=t)
                | Q(_n_city__contains=t)
                | Q(_n_district__contains=t)
                | Q(_n_category__contains=t)
                | Q(_n_service__contains=t)
            )

        return qs.distinct()

    def filter_city(self, queryset, name, value):
        """İl filtresi: büyük/küçük harf ve Türkçe/Latince duyarsız (örn. istanbul = İstanbul)."""
        raw = (value or "").strip()
        if not raw:
            return queryset
        norm = _normalize_tr(raw)
        qs = queryset.annotate(_n_city=_norm_db_expr("city"))
        return qs.filter(_n_city=norm).distinct()

    def filter_district(self, queryset, name, value):
        """İlçe filtresi: büyük/küçük harf ve Türkçe/Latince duyarsız."""
        raw = (value or "").strip()
        if not raw:
            return queryset
        norm = _normalize_tr(raw)
        qs = queryset.annotate(_n_district=_norm_db_expr("district"))
        return qs.filter(_n_district=norm).distinct()

    def filter_gender(self, queryset, name, value):
        """
        Gender filtresi: erkek veya kadın seçildiğinde unisex kuaförler de dahil edilir.
        Unisex kuaförler hem erkek hem kadın için hizmet verdiği için her durumda gösterilmelidir.
        """
        if not value:
            return queryset
        
        value_lower = value.lower()
        
        # Erkek seçildiğinde: erkek VE unisex kuaförler
        if value_lower in ['male', 'erkek']:
            return queryset.filter(Q(gender__iexact='male') | Q(gender__iexact='unisex'))
        
        # Kadın seçildiğinde: kadın VE unisex kuaförler
        elif value_lower in ['female', 'kadın', 'kadin']:
            return queryset.filter(Q(gender__iexact='female') | Q(gender__iexact='unisex'))
        
        # Unisex direkt seçilirse sadece unisex
        else:
            return queryset.filter(gender__iexact=value)

    def filter_is_open(self, queryset, name, value):
        if not value:
            return queryset

        now = timezone.localtime()
        # Weekday keys in ShopWorkingHours are MON, TUE, etc.
        # strftime("%a") returns Mon, Tue...
        current_day_code = now.strftime("%a").upper()
        current_time = now.time()

        return queryset.filter(
            shop_working_hours__day_of_week=current_day_code,
            shop_working_hours__is_closed=False,
            shop_working_hours__start_time__lte=current_time,
            shop_working_hours__end_time__gte=current_time
        ).distinct()


