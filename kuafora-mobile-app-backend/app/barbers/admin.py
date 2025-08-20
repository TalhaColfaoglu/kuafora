from django.contrib import admin
from .models import (
    Barbershop,
    BarbershopImage,
    Staff,
    StaffCatalogImage,
    WorkSchedule,
    Review,
    Service,
    Favorite,
)


class BarbershopImageInline(admin.TabularInline):
    model = BarbershopImage
    extra = 1


@admin.register(Barbershop)
class BarbershopAdmin(admin.ModelAdmin):
    list_display = ("name", "gender", "city", "district", "is_verified", "rating_avg", "total_reviews")
    list_filter = ("gender", "city", "district", "is_verified")
    search_fields = ("name", "city", "district")
    inlines = [BarbershopImageInline]


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("barbershop", "email", "certificate", "is_admin", "total_reviews")
    list_filter = ("barbershop", "certificate", "is_admin")
    search_fields = ("email",)


@admin.register(StaffCatalogImage)
class StaffCatalogImageAdmin(admin.ModelAdmin):
    list_display = ("staff", "id")


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ("staff", "day_of_week", "start_time", "end_time", "break_time")
    list_filter = ("day_of_week",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "barbershop", "rating", "created_at")
    list_filter = ("rating",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("barbershop", "category", "name", "price", "duration", "is_active")
    list_filter = ("barbershop", "category", "is_active")
    search_fields = ("name", "category")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "barbershop", "created_at")


