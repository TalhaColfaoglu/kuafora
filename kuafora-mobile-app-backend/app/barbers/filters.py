from django_filters import rest_framework as filters
from django.utils import timezone
from django.db.models import Q, F, Value
from django.db.models.functions import Lower, Replace
from .models import Barbershop, ShopCategory


class BarbershopFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_q")
    city = filters.CharFilter(field_name="city", lookup_expr="iexact")
    district = filters.CharFilter(field_name="district", lookup_expr="iexact")
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
        - Turkish character tolerant: i/ı, s/ş, g/ğ, u/ü, o/ö, c/ç
        - Tokenized search across: name, city, district, category name, service name
        - Supports "istanbul kadikoy berber" style queries.
        """
        raw = (value or "").strip()
        if not raw:
            return queryset

        def normalize_tr(s: str) -> str:
            s = (s or "").strip().lower()
            # Remove Turkish-specific chars to ASCII equivalents
            s = (
                s.replace("ı", "i")
                .replace("ş", "s")
                .replace("ğ", "g")
                .replace("ü", "u")
                .replace("ö", "o")
                .replace("ç", "c")
            )
            # keep only single spaces
            s = " ".join(s.split())
            return s

        def norm_db(field_name: str):
            expr = Lower(F(field_name))
            expr = Replace(expr, Value("ı"), Value("i"))
            expr = Replace(expr, Value("ş"), Value("s"))
            expr = Replace(expr, Value("ğ"), Value("g"))
            expr = Replace(expr, Value("ü"), Value("u"))
            expr = Replace(expr, Value("ö"), Value("o"))
            expr = Replace(expr, Value("ç"), Value("c"))
            return expr

        q_norm = normalize_tr(raw)
        tokens = [t for t in q_norm.split(" ") if t]
        if not tokens:
            return queryset

        qs = queryset.annotate(
            _n_name=norm_db("name"),
            _n_city=norm_db("city"),
            _n_district=norm_db("district"),
            _n_category=norm_db("categories__name"),
            _n_service=norm_db("services__name"),
        )

        # Each token must match at least one of the searchable fields (AND across tokens).
        for t in tokens:
            qs = qs.filter(
                Q(_n_name__contains=t)
                | Q(_n_city__contains=t)
                | Q(_n_district__contains=t)
                | Q(_n_category__contains=t)
                | Q(_n_service__contains=t)
            )

        return qs.distinct()

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


