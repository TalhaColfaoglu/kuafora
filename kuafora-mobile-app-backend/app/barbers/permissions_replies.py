from rest_framework.permissions import BasePermission

class IsReplyOwnerOrShopAdmin(BasePermission):
    """
    Kullanıcı yanıtın sahibi ise veya yanıtın ait olduğu salonun admin'i ise izin ver.
    """
    def has_object_permission(self, request, view, obj):
        # Yanıtın sahibi ise izin ver
        if obj.user == request.user:
            return True
        
        # Yanıtın ait olduğu salonun admin'i ise izin ver
        # Review -> Barbershop -> Staff -> User check
        try:
            barbershop = obj.review.barbershop
            return request.user.staff_profiles.filter(
                barbershop=barbershop, 
                is_admin=True
            ).exists()
        except:
            return False

