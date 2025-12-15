from django_filters import rest_framework as filters
from django.utils import timezone
from django.db.models import Q
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
        return queryset.filter(name__icontains=value)

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


