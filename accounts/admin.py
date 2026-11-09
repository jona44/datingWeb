from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile, ProfilePhoto, PhoneVerification


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('phone_number', 'email', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    ordering = ('phone_number',)
    fieldsets = (
        (None, {'fields': ('phone_number', 'email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'email', 'password'),
        }),
    )
    search_fields = ('phone_number', 'email')


class ProfilePhotoInline(admin.TabularInline):
    model = ProfilePhoto
    extra = 1


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user_phone', 'user_email', 'app_variant', 'is_complete', 'onboarding_step', 'created_at')
    list_filter = ('app_variant', 'is_complete', 'gender', 'treatment_status', 'is_verified')
    search_fields = ('display_name', 'user__phone_number', 'user__email', 'city')
    inlines = [ProfilePhotoInline]

    def user_phone(self, obj):
        return str(obj.user.phone_number)
    user_phone.short_description = 'Phone'

    def user_email(self, obj):
        return obj.user.email or "-"
    user_email.short_description = 'Email'


@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'is_verified', 'attempts', 'created_at', 'expires_at', 'ip_address')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('phone_number', 'ip_address')
    readonly_fields = ('created_at',)
