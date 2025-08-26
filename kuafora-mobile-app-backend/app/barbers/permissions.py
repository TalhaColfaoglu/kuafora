from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsShopAdmin(BasePermission):
    message = "Only barbershop admins can perform this action."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        # Allow creating a new barbershop without admin privilege.
        # The creator will be attached as admin in PartnerBarbershopViewSet.perform_create.
        action = getattr(view, 'action', None)
        view_name = view.__class__.__name__
        if view_name == 'PartnerBarbershopViewSet' and action == 'create':
            return request.user and request.user.is_authenticated
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Partner access means having any Staff profile with is_admin=True
        return user.staff_profiles.filter(is_admin=True).exists() or user.is_superuser


