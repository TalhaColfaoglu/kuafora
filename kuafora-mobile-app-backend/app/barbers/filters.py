from django_filters import rest_framework as filters
from django.utils import timezone
from .models import Barbershop, ShopCategory


class BarbershopFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_q")
    city = filters.CharFilter(field_name="city", lookup_expr="iexact")
    district = filters.CharFilter(field_name="district", lookup_expr="iexact")
    gender = filters.CharFilter(field_name="gender", lookup_expr="iexact")
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


