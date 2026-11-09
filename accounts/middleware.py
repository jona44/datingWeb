from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile:
                from .services import update_last_seen
                update_last_seen(profile)
        
        return self.get_response(request)


class ProfileCompletionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Avoid redirect loop for onboarding, welcome, logout, static assets, and admin
            logout_url = reverse("logout")
            welcome_url = reverse("welcome")
            
            is_onboarding_path = request.path.startswith("/accounts/onboarding/")
            is_admin_path = request.path.startswith("/admin/")
            is_static_path = request.path.startswith("/static/") or request.path.startswith("/media/")
            
            if request.path not in [logout_url, welcome_url] and not is_onboarding_path and not is_admin_path and not is_static_path:
                # Admins and staff don't need to complete profiles to access tools
                if request.user.is_staff or request.user.is_superuser:
                    return self.get_response(request)

                profile = getattr(request.user, "profile", None)
                if profile:
                    if not profile.is_complete:
                        step = max(1, profile.onboarding_step)
                        return redirect("onboarding_step", step=step)

        return self.get_response(request)
