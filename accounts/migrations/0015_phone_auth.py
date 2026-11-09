import uuid
from django.db import migrations, models
import phonenumber_field.modelfields


def populate_phone_numbers(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for idx, user in enumerate(User.objects.all(), start=1):
        user.phone_number = f"+2782{idx:07d}"
        user.save(update_fields=['phone_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_profile_app_variant'),
    ]

    operations = [
        # Step 1: Add phone_number as nullable
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=phonenumber_field.modelfields.PhoneNumberField(
                max_length=128,
                null=True,
                region=None,
            ),
        ),
        # Step 2: Backfill existing users with mock phone numbers
        migrations.RunPython(populate_phone_numbers, reverse_code=migrations.RunPython.noop),
        # Step 3: Enforce unique and non-null on phone_number
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=phonenumber_field.modelfields.PhoneNumberField(
                db_index=True,
                max_length=128,
                unique=True,
                region=None,
            ),
        ),
        # Step 4: Make email optional and nullable
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(
                blank=True,
                max_length=254,
                null=True,
                unique=True,
            ),
        ),
        # Step 5: Create PhoneVerification model
        migrations.CreateModel(
            name='PhoneVerification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('phone_number', phonenumber_field.modelfields.PhoneNumberField(db_index=True, max_length=128, region=None)),
                ('otp_hash', models.CharField(max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('is_verified', models.BooleanField(default=False)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['phone_number', '-created_at'], name='accounts_ph_phone_n_9c1cb3_idx'),
                ],
            },
        ),
    ]

