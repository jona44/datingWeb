import json
import os
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from discovery.forms import PreferenceForm
from discovery.models import Preference
from .constants import GEOGRAPHIC_DATA
from .forms import (
    OnboardingStep1Form,
    OnboardingStep2Form,
    OnboardingStep3Form,
    OnboardingStep4Form,
    ProfileForm,
)
from .models import PhoneVerification, Profile, ProfilePhoto, User


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def normalize_phone(raw_phone, default_region='ZA'):
    raw_phone = str(raw_phone).strip()
    try:
        parsed = phonenumbers.parse(raw_phone, default_region)
        if not phonenumbers.is_valid_number(parsed):
            return None, "Invalid phone number format."
        formatted = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        return formatted, None
    except NumberParseException:
        return None, "Could not parse phone number. Please include a valid country code (e.g. +27 or +263)."


@login_required
def home(request, variant=None):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.is_complete:
        step = max(1, profile.onboarding_step)
        return redirect("onboarding_step", step=step)
    return redirect("discovery_feed")


@login_required
def welcome_view(request):
    """Welcome page after signup"""
    return render(request, "accounts/welcome.html")


@login_required
def onboarding_step_view(request, step):
    """Handle multi-step onboarding"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    # Determine variant
    variant = getattr(request, 'app_variant', os.getenv('APP_VARIANT', 'hiv_plus'))
    
    # If general variant and trying to access step 3, redirect to step 4
    if variant == 'general' and step == 3:
        return redirect('onboarding_step', step=4)
        
    # Define forms for each step
    forms_map = {
        1: OnboardingStep1Form,
        2: OnboardingStep2Form,
        3: OnboardingStep3Form,  # HIV Journey - Optional
        4: OnboardingStep4Form,
    }
    
    # Validate step number
    if step not in forms_map:
        return redirect('onboarding_step', step=1)
    
    FormClass = forms_map[step]
    
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.onboarding_step = step
            profile.profile_completeness = profile.calculate_completeness()
            
            # Mark complete on final step
            if step == 4:
                profile.is_complete = True
                
            profile.save()
            
            # Handle additional photos for Step 4
            if step == 4:
                files = request.FILES.getlist('additional_photos')
                for f in files:
                    ProfilePhoto.objects.create(profile=profile, image=f)
            
            # Navigate to next step or complete
            if step < 4:
                next_step = step + 1
                # Skip step 3 for general variant
                if variant == 'general' and next_step == 3:
                    next_step = 4
                return redirect('onboarding_step', step=next_step)
            else:
                messages.success(request, 'Welcome! Your profile is complete.')
                return redirect('discovery_feed')
    else:
        form = FormClass(instance=profile)
    
    # Clean geographic data for JSON (ensure keys matches dropdown values)
    clean_geo_data = {k.strip(): v for k, v in GEOGRAPHIC_DATA.items()}
    
    # Adjust total steps and current display step for progress bar
    total_steps = 4 if variant == 'hiv_plus' else 3
    display_step = step
    if variant == 'general' and step == 4:
        display_step = 3
        
    return render(request, f'accounts/onboarding/step{step}.html', {
        'form': form,
        'step': display_step,
        'actual_step': step,
        'total_steps': total_steps,
        'progress': int((display_step / total_steps) * 100),
        'geographic_data': json.dumps(clean_geo_data) if step in [1, 2] else "{}"
    })


@login_required
def edit_profile(request):
    """Allow users to edit their profile and match preferences"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    preferences, _ = Preference.objects.get_or_create(profile=profile)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        pref_form = PreferenceForm(request.POST, instance=preferences)
        
        if form.is_valid() and pref_form.is_valid():
            prof = form.save(commit=False)
            prof.user = request.user
            prof.profile_completeness = prof.calculate_completeness()
            prof.save()
            pref_form.save()
            
            # Handle additional photos
            files = request.FILES.getlist('additional_photos')
            for f in files:
                ProfilePhoto.objects.create(profile=profile, image=f)
            
            messages.success(request, "Profile and preferences updated successfully!")
            return redirect("edit_profile")
    else:
        form = ProfileForm(instance=profile)
        pref_form = PreferenceForm(instance=preferences)

    # Clean geographic data for JSON
    clean_geo_data = {k.strip(): v for k, v in GEOGRAPHIC_DATA.items()}

    return render(request, "accounts/edit_profile.html", {
        "form": form,
        "pref_form": pref_form,
        "profile": profile,
        "geographic_data": json.dumps(clean_geo_data)
    })


def login_view(request):
    """Unified Passwordless Phone Login/Signup Page"""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "accounts/login.html", {"mode": "login"})


def signup_view(request):
    """Unified Passwordless Phone Signup redirects to the unified auth page"""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "accounts/login.html", {"mode": "signup"})


def logout_view(request):
    logout(request)
    return redirect("login")


@require_POST
def send_otp_view(request):
    """AJAX endpoint: Send OTP to provided phone number"""
    raw_phone = request.POST.get("phone_number", "").strip()
    if not raw_phone:
        return JsonResponse({"success": False, "error": "Please enter a valid phone number."}, status=400)

    default_region = getattr(settings, 'PHONENUMBER_DEFAULT_REGION', 'ZA')
    formatted_phone, err = normalize_phone(raw_phone, default_region)
    if err:
        return JsonResponse({"success": False, "error": err}, status=400)

    ip_address = get_client_ip(request)

    try:
        record, code = PhoneVerification.request_otp(formatted_phone, ip_address=ip_address)
        return JsonResponse({
            "success": True,
            "message": "Verification code sent.",
            "phone_number": formatted_phone,
            "expires_in": getattr(settings, 'OTP_EXPIRATION_SECONDS', 300)
        })
    except ValidationError as e:
        return JsonResponse({"success": False, "error": e.message}, status=429)
    except Exception as e:
        return JsonResponse({"success": False, "error": "Unable to send verification code right now. Please try again."}, status=500)


@require_POST
def verify_otp_view(request):
    """AJAX endpoint: Verify OTP and log in / register user"""
    raw_phone = request.POST.get("phone_number", "").strip()
    code = request.POST.get("otp", "").strip()

    if not raw_phone or not code:
        return JsonResponse({"success": False, "error": "Phone number and verification code are required."}, status=400)

    default_region = getattr(settings, 'PHONENUMBER_DEFAULT_REGION', 'ZA')
    formatted_phone, err = normalize_phone(raw_phone, default_region)
    if err:
        return JsonResponse({"success": False, "error": err}, status=400)

    is_valid, message = PhoneVerification.verify_otp(formatted_phone, code)
    if not is_valid:
        return JsonResponse({"success": False, "error": message}, status=400)

    # User lookup or creation
    created = False
    try:
        user = User.objects.get(phone_number=formatted_phone)
    except User.DoesNotExist:
        user = User.objects.create_user(phone_number=formatted_phone)
        created = True

    # Variant isolation check
    req_variant = getattr(request, 'app_variant', os.getenv('APP_VARIANT', 'hiv_plus'))
    profile, _ = Profile.objects.get_or_create(user=user)

    if not created and profile.app_variant and profile.app_variant != req_variant:
        return JsonResponse({
            "success": False,
            "error": "This account is registered for a different community variant."
        }, status=403)

    if created:
        profile.app_variant = req_variant
        profile.save()

    # Log in the user
    login(request, user, backend='accounts.backends.PhoneOTPBackend')

    if not profile.is_complete:
        step = max(1, profile.onboarding_step)
        redirect_url = reverse("onboarding_step", kwargs={"step": step})
    else:
        redirect_url = reverse("discovery_feed")

    return JsonResponse({
        "success": True,
        "message": "Authenticated successfully.",
        "redirect_url": redirect_url,
        "is_new_user": created
    })


@login_required
def delete_photo_view(request, photo_id):
    """Delete a profile photo"""
    if request.method == "DELETE":
        photo = get_object_or_404(ProfilePhoto, id=photo_id, profile__user=request.user)
        photo.delete()
        return HttpResponse("")
    return HttpResponse(status=405)
