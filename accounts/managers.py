import hashlib
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, phone_number=None, email=None, password=None, **extra_fields):
        # Handle positional or kwarg username if legacy call occurs
        if not phone_number and 'username' in extra_fields:
            phone_number = extra_fields.pop('username')

        # Backward compatibility for legacy tests or scripts passing email without phone_number
        if not phone_number:
            if email:
                digest = int(hashlib.md5(str(email).lower().encode('utf-8')).hexdigest()[:8], 16) % 9000000 + 1000000
                phone_number = f"+2782{digest:07d}"
            else:
                raise ValueError("Phone number is required")

        phone_number = str(phone_number).strip().replace(" ", "")

        normalized_email = self.normalize_email(email) if email else None

        user = self.model(
            phone_number=phone_number,
            email=normalized_email,
            **extra_fields
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number=None, password=None, email=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if not password:
            raise ValueError('Superusers must set a password for admin dashboard access.')

        return self.create_user(phone_number=phone_number, email=email, password=password, **extra_fields)
