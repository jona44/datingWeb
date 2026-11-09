from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class PhoneOTPBackend(ModelBackend):
    """
    Authenticate a user by verified phone number without password.
    """
    def authenticate(self, request, phone_number=None, **kwargs):
        if not phone_number:
            return None
        try:
            # Clean / normalize phone format
            normalized_phone = str(phone_number).strip().replace(" ", "")
            user = User.objects.get(phone_number=normalized_phone)
            if self.user_can_authenticate(user):
                return user
        except User.DoesNotExist:
            return None
        except Exception:
            return None
        return None

