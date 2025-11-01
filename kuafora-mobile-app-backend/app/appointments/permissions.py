from rest_framework.permissions import BasePermission


class IsBookingEnabled(BasePermission):
    message = "BOOKING_DISABLED"

    def has_permission(self, request, view):  # type: ignore[override]
        shop = getattr(view, "shop", None)
        if shop is None:
            # Try to infer from staff or payload later in view logic; allow here
            return True
        return getattr(shop, "system_type", "info") == "booking"


