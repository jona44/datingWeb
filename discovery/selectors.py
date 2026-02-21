from accounts.models import Profile
from interactions.models import Like, Match, Skip, Block
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q


def get_discovery_profiles(for_profile, limit=10):
    """Get profiles for discovery feed, filtered by user preferences"""
    excluded_profiles = set()

    # Exclude matched profiles
    excluded_profiles.update(
        Match.objects.filter(profile1=for_profile)
        .values_list('profile2__id', flat=True)
    )
    excluded_profiles.update(
        Match.objects.filter(profile2=for_profile)
        .values_list('profile1__id', flat=True)
    )
    
    # Exclude skipped profiles
    excluded_profiles.update(
        Skip.objects.filter(from_profile=for_profile)
        .values_list('to_profile_id', flat=True)
    )

    # Exclude blocked/blocker profiles
    excluded_profiles.update(
        Block.objects.filter(blocker=for_profile)
        .values_list('blocked_id', flat=True)
    )
    excluded_profiles.update(
        Block.objects.filter(blocked=for_profile)
        .values_list('blocker_id', flat=True)
    )

    # Get user's preferences
    try:
        prefs = for_profile.preferences
    except:
        # If no preferences exist, create default ones
        from .models import Preference
        prefs = Preference.objects.create(profile=for_profile)

    # Build queryset with preference filters
    from django.db.models import Exists, OuterRef
    queryset = (
        Profile.objects
        .filter(is_visible=True, user__is_active=True, is_complete=True)
        .exclude(id__in=excluded_profiles)
        .exclude(id=for_profile.id)
        .annotate(
            is_liked=Exists(Like.objects.filter(from_profile=for_profile, to_profile=OuterRef('pk')))
        )
    )

    if for_profile.app_variant:
        queryset = queryset.filter(app_variant=for_profile.app_variant)

    # Filter by age if birth_date is set
    if prefs.min_age and prefs.max_age:
        today = timezone.now().date()
        min_birth_date = today - timedelta(days=prefs.max_age * 365.25)
        max_birth_date = today - timedelta(days=prefs.min_age * 365.25)
        queryset = queryset.filter(
            birth_date__isnull=False,
            birth_date__gte=min_birth_date,
            birth_date__lte=max_birth_date
        )

    # Filter by gender preference
    if prefs.interested_in and prefs.interested_in != 'all':
        queryset = queryset.filter(gender=prefs.interested_in)

    # Filter by ethnicity preference
    if prefs.pref_ethnicity and prefs.pref_ethnicity != 'any':
        queryset = queryset.filter(ethnicity=prefs.pref_ethnicity)

    # Filter by city preference
    if prefs.pref_city:
        queryset = queryset.filter(city__icontains=prefs.pref_city)

    # Filter by children count preference
    if prefs.pref_max_children is not None:
        queryset = queryset.filter(children_count__lte=prefs.pref_max_children)

    # Filter by nationality preference (using icontains for flexibility)
    if prefs.pref_nationality and prefs.pref_nationality.lower() != 'any':
        queryset = queryset.filter(nationality__icontains=prefs.pref_nationality)

    # Only show profiles that have opted into discovery
    queryset = queryset.filter(preferences__show_me=True)

    return queryset.order_by('?')[:limit]  # Random order


def search_profiles(query, for_profile=None):
    """Search for profiles by name, location, or bio"""
    queryset = Profile.objects.filter(
        is_complete=True,
        is_visible=True,
        user__is_active=True
    )
    
    # Exclude self if for_profile is provided
    if for_profile:
        queryset = queryset.exclude(id=for_profile.id)
        if for_profile.app_variant:
            queryset = queryset.filter(app_variant=for_profile.app_variant)
    
    # Search across multiple fields
    if query:
        queryset = queryset.filter(
            Q(display_name__icontains=query) |
            Q(location__icontains=query) |
            Q(bio__icontains=query) |
            Q(gender__icontains=query)
        )
    
    return queryset.select_related('user')[:50]  # Limit results
