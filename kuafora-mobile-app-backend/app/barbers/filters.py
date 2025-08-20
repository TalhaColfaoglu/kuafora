from django_filters import rest_framework as filters
from .models import Barbershop


class BarbershopFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_q")
    city = filters.CharFilter(field_name="city", lookup_expr="iexact")
    district = filters.CharFilter(field_name="district", lookup_expr="iexact")
    gender = filters.CharFilter(field_name="gender", lookup_expr="iexact")

    class Meta:
        model = Barbershop
        fields = ("q", "city", "district", "gender")

    def filter_q(self, queryset, name, value):
        return queryset.filter(name__icontains=value)


