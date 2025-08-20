from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsShopAdmin(BasePermission):
    message = "Only barbershop admins can perform this action."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Partner access means having any Staff profile with is_admin=True
        return user.staff_profiles.filter(is_admin=True).exists() or user.is_superuser


