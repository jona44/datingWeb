import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

print("Resetting all user passwords to 'munyaradzi'...")
count = 0
for user in User.objects.all():
    user.set_password('munyaradzi')
    user.save()
    count += 0
print(f"Successfully reset {count} users.")