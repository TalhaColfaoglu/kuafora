from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        login_identifier = email or username
        if login_identifier is None:
            return None
        try:
            user = User.objects.get(email__iexact=login_identifier)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


