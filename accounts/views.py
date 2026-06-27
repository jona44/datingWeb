import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404, HttpResponse
from .forms import (
    ProfileForm, SignupForm, OnboardingStep1Form, 
    OnboardingStep2Form, OnboardingStep3Form, OnboardingStep4Form
)
from .constants import GEOGRAPHIC_DATA
from discovery.forms import PreferenceForm
from discovery.models import Preference
from .models import Profile, ProfilePhoto
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


@login_required
def home(request, variant=None):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.is_complete:
        step = max(1, profile.onboarding_step)
        return redirect("onboarding_step", step=step)
    if variant:
        return redirect(f"/{variant}/discover/")
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
    import os
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
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user:
            import os
            req_variant = getattr(request, 'app_variant', os.getenv('APP_VARIANT', 'hiv_plus'))
            if hasattr(user, 'profile') and user.profile.app_variant and user.profile.app_variant != req_variant:
                messages.error(request, "Account registered for a different community variant.")
            else:
                login(request, user)
                return redirect("home")
        else:
            messages.error(request, "Invalid email or password")

    return render(request, "accounts/login.html")



def logout_view(request):
    logout(request)
    return redirect("login")




def signup_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Ensure the profile belongs to the correct app variant
            if hasattr(user, 'profile'):
                import os
                user.profile.app_variant = getattr(request, 'app_variant', os.getenv('APP_VARIANT', 'hiv_plus'))
                user.profile.save()
                
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect("welcome")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def delete_photo_view(request, photo_id):
    """Delete a profile photo"""
    if request.method == "DELETE":
        photo = get_object_or_404(ProfilePhoto, id=photo_id, profile__user=request.user)
        photo.delete()
        return HttpResponse("")
    return HttpResponse(status=405)