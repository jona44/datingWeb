from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile, ProfilePhoto

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('email', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password'),
        }),
    )
    search_fields = ('email',)

class ProfilePhotoInline(admin.TabularInline):
    model = ProfilePhoto
    extra = 1

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user_email', 'app_variant', 'is_complete', 'onboarding_step', 'created_at')
    list_filter = ('app_variant', 'is_complete', 'gender', 'treatment_status', 'is_verified')
    search_fields = ('display_name', 'user__email', 'city')
    inlines = [ProfilePhotoInline]
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

