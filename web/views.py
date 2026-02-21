import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db import models
from accounts.selectors import get_profile_for_user
from accounts.models import Profile
from discovery.selectors import get_discovery_profiles, search_profiles
from discovery.models import Preference
from discovery.forms import PreferenceForm
from accounts.constants import GEOGRAPHIC_DATA
from interactions.services import handle_like
from messaging.selectors import get_conversations_for_profile, get_conversation
from messaging.services import send_message
from messaging.models import Conversation
from messaging.services import mark_conversation_as_read
from accounts.services import update_last_seen
from messaging.typing import set_typing, is_typing
from accounts.presence import mark_online
from interactions.models import Match


@login_required
def discovery_feed(request):
    profile = get_profile_for_user(request.user)
    profiles = get_discovery_profiles(profile)
    
    context = {'profiles': profiles}
    
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'discovery-feed':
        return render(request, 'web/discovery/partials/feed_grid.html', context)

    return render(request, 'web/discovery/feed.html', context)


@login_required
def like_profile_view(request, profile_id):
    actor = get_profile_for_user(request.user)
    target = get_object_or_404(Profile, id=profile_id)

    match = handle_like(actor, target)

    if match:
        context = {
            'profile': target,
            'matched': True,
        }
        return render(request, 'web/discovery/partials/like_result.html', context)
    
    source = request.GET.get('source')
    if source == 'card':
        # If liked from card, return the updated card with grayed out button
        target.is_liked = True
        return render(request, 'web/discovery/partials/profile_card.html', {'profile': target})
    
    # If not a match and not from card (e.g. from modal), return the standard message
    return render(request, 'web/discovery/partials/like_result.html', {'profile': target, 'matched': False})


@login_required
def skip_profile_view(request, profile_id):
    """Skip a profile - just return an empty response to hide the card"""
    return render(request, 'web/discovery/partials/skip_result.html')


@login_required
def profile_view(request, profile_id):
    """View full profile details"""
    profile = get_object_or_404(Profile, id=profile_id)
    viewer = get_profile_for_user(request.user)
    
    # Calculate age if birth_date exists
    age = None
    if profile.birth_date:
        from datetime import date
        today = date.today()
        age = today.year - profile.birth_date.year - ((today.month, today.day) < (profile.birth_date.month, profile.birth_date.day))
    
    from interactions.models import Like
    is_liked = Like.objects.filter(from_profile=viewer, to_profile=profile).exists()
    
    # Record view
    from interactions.services import record_profile_view
    record_profile_view(viewer, profile)

    context = {
        'profile': profile,
        'age': age,
        'viewer': viewer,
        'is_liked': is_liked,
    }
    
    # Return modal template for HTMX requests
    if request.headers.get('HX-Request'):
        response = render(request, 'web/discovery/profile_detail_modal.html', context)
        response['HX-Trigger-After-Settle'] = json.dumps({'modal-open': {}})
        return response
    
    return render(request, 'web/discovery/profile_detail.html', context)


@login_required
def block_user_view(request, profile_id):
    """Block a user"""
    from interactions.services import block_user
    from django.contrib import messages
    
    viewer = get_profile_for_user(request.user)
    target = get_object_or_404(Profile, id=profile_id)
    
    block_user(viewer, target)
    messages.success(request, f"You have blocked {target.display_name|default:target.user.email}")
    
    return redirect('discovery_feed')


@login_required
def report_user_view(request, profile_id):
    """Report a user"""
    from interactions.services import report_user
    from django.contrib import messages
    
    viewer = get_profile_for_user(request.user)
    target = get_object_or_404(Profile, id=profile_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'other')
        description = request.POST.get('description', '')
        
        report_user(viewer, target, reason, description)
        messages.success(request, "Thank you for your report. We'll review it shortly.")
        return redirect('discovery_feed')
    
    return render(request, 'web/discovery/report.html', {
        'profile': target,
    })


@login_required
def inbox(request):
    profile = get_profile_for_user(request.user)

    matches = Match.objects.filter(
        profile1=profile
    ) | Match.objects.filter(
        profile2=profile
    )
    
    # Since profile belongs to one variant, any match involving it should inherently be the same variant. 
    # But for extra safety on older data:
    if profile.app_variant:
        matches = matches.filter(
            models.Q(profile1__app_variant=profile.app_variant) & 
            models.Q(profile2__app_variant=profile.app_variant)
        )

    matches = matches.order_by("-created_at")

    # Annotate with 'other' user and conversation for template
    for m in matches:
        m.other = m.other_profile(profile)
        # Find conversation between these two profiles
        m.conversation = (
            Conversation.objects
            .filter(participants=profile)
            .filter(participants=m.other)
            .first()
        )
        
        # Calculate unread count for this conversation
        if m.conversation:
            from messaging.selectors import get_unread_count_for_conversation
            m.unread_count = get_unread_count_for_conversation(m.conversation, profile)
        else:
            m.unread_count = 0

    return render(request, "web/messaging/inbox.html", {
        "matches": matches,
    })



@login_required
def send_message_view(request, conversation_id):
    profile = get_profile_for_user(request.user)
    conversation = get_object_or_404(Conversation, id=conversation_id)

    body = request.POST.get('body')
    message = send_message(profile, conversation, body)

    return render(request, 'web/messaging/partials/message.html', {
        'message': message,
        'profile': profile
    })

@login_required
def conversation_detail(request, conversation_id):
    profile = get_profile_for_user(request.user)
    mark_online(profile.id)

    conversation = get_object_or_404(Conversation, id=conversation_id)

    if not conversation.participants.filter(id=profile.id).exists():
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    # domain updates
    mark_conversation_as_read(profile, conversation)
    update_last_seen(profile)

    # read-only selectors
    from messaging.selectors import get_messages_with_read_state
    # (Checking if get_presence_map is needed, but it was in the duplicate)
    # For now, let's just make it work.
    chat_messages = get_messages_with_read_state(conversation, profile)
    
    return render(request, 'web/messaging/conversation.html', {
        'conversation': conversation,
        'chat_messages': chat_messages,
        'profile': profile,
    })



@login_required
def typing_ping(request, conversation_id):
    profile = get_profile_for_user(request.user)
    mark_online(profile.id)
    conversation = get_object_or_404(Conversation, id=conversation_id)

    if not conversation.participants.filter(id=profile.id).exists():
        raise PermissionDenied

    set_typing(conversation.id, profile.id)

    return render(
        request,
        'web/messaging/partials/typing_indicator.html',
        {'typing': False}
    )


@login_required
def typing_status(request, conversation_id):
    profile = get_profile_for_user(request.user)
    conversation = get_object_or_404(Conversation, id=conversation_id)

    other = conversation.participants.exclude(id=profile.id).first()

    typing = is_typing(conversation.id, other.id) if other else False

    return render(
        request,
        'web/messaging/partials/typing_indicator.html',
        {'typing': typing}
    )





@login_required
def preferences_view(request):
    """View and edit user's discovery preferences"""
    profile = get_profile_for_user(request.user)
    
    # Get or create preferences
    preferences, created = Preference.objects.get_or_create(profile=profile)
    
    is_htmx = request.headers.get('HX-Request')
    
    if request.method == 'POST':
        form = PreferenceForm(request.POST, instance=preferences)
        if form.is_valid():
            saved_prefs = form.save(commit=True)
            
            # Debug logging
            print(f"[DEBUG] Preferences saved for profile {profile.id}:")
            print(f"  min_age: {saved_prefs.min_age}")
            print(f"  max_age: {saved_prefs.max_age}")
            print(f"  interested_in: {saved_prefs.interested_in}")
            
            # Explicitly refresh from DB to verify save
            saved_prefs.refresh_from_db()
            print(f"[DEBUG] After refresh_from_db - min_age: {saved_prefs.min_age}")
            
            if is_htmx:
                # Return empty response with HX-Trigger to close slideover and show toast
                from django.http import HttpResponse
                
                response = HttpResponse(status=200)
                response['HX-Trigger'] = json.dumps({
                    "toast": {
                        "type": "success",
                        "title": "Preferences saved!",
                        "message": "Your match criteria has been updated."
                    },
                    "slideover-close": {},
                    "discovery-refresh": {}
                })
                return response
            
            return redirect('discovery_feed')
    else:
        form = PreferenceForm(instance=preferences)
    
    # Clean geographic data for JSON
    clean_geo_data = {k.strip(): v for k, v in GEOGRAPHIC_DATA.items()}
    print(f"DEBUG: geographic_data keys: {list(clean_geo_data.keys())}")
    
    # Return slide-over template for HTMX requests
    if is_htmx:
        context = {
            'form': form,
            'geographic_data': json.dumps(clean_geo_data)
        }
        response = render(request, 'web/discovery/preferences_panel.html', context)
        response['HX-Trigger-After-Settle'] = json.dumps({'slideover-open': {}})
        return response
    
    return render(request, 'web/discovery/preferences.html', {
        'form': form,
        'geographic_data': json.dumps(clean_geo_data)
    })


@login_required
def search_view(request):
    """Search for profiles"""
    profile = get_profile_for_user(request.user)
    query = request.GET.get('q', '').strip()
    
    results = []
    if query:
        results = search_profiles(query, for_profile=profile)
    
    return render(request, 'web/discovery/search.html', {
        'query': query,
        'results': results,
    })
from accounts.forms import UserSettingsForm

@login_required
def settings_view(request):
    """General account settings"""
    profile = get_profile_for_user(request.user)
    
    is_htmx = request.headers.get('HX-Request')
    
    if request.method == 'POST':
        if 'delete_account' in request.POST:
            user = request.user
            user.delete()
            return redirect('welcome')
            
        form = UserSettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            
            if is_htmx:
                # Return success toast and re-render form
                from django.http import HttpResponse
                response = render(request, 'web/settings.html', {'form': form})
                response['HX-Trigger'] = '{"toast": {"type": "success", "title": "Settings saved!", "message": "Your preferences have been updated."}}'
                return response
            
            from django.contrib import messages
            messages.success(request, "Settings updated successfully.")
            return redirect('settings')
    else:
        form = UserSettingsForm(instance=profile)
        
    return render(request, 'web/settings.html', {
        'form': form,
    })


@login_required
def activity_view(request):
    """View who liked me and who recently viewed my profile"""
    profile = get_profile_for_user(request.user)
    
    from interactions.models import Like, Match, ProfileView
    
    # 1. Who liked me (and we haven't matched yet)
    # Get everyone who liked me
    likers_ids = Like.objects.filter(to_profile=profile).values_list('from_profile_id', flat=True)
    
    # Get everyone I already matched with
    matched_ids = Match.objects.filter(
        models.Q(profile1=profile) | models.Q(profile2=profile)
    ).values_list('profile1_id', 'profile2_id')
    
    # Flatten match IDs and exclude self
    matched_set = set()
    for p1, p2 in matched_ids:
        matched_set.add(p1)
        matched_set.add(p2)
    if profile.id in matched_set:
        matched_set.remove(profile.id)
        
    # Filter likers to exclude those already matched & enforce variant
    likers = Profile.objects.filter(id__in=likers_ids).exclude(id__in=matched_set)
    if profile.app_variant:
        likers = likers.filter(app_variant=profile.app_variant)
    likers = likers.distinct()
    
    # 2. Who recently viewed me
    # Group by viewer and get the most recent view time
    recent_visitors = ProfileView.objects.filter(viewed=profile).values('viewer').annotate(
        last_view=models.Max('created_at')
    ).order_by('-last_view')[:50]
    
    visitor_ids = [v['viewer'] for v in recent_visitors]
    visitors_qs = Profile.objects.filter(id__in=visitor_ids)
    if profile.app_variant:
        visitors_qs = visitors_qs.filter(app_variant=profile.app_variant)
    visitors = {p.id: p for p in visitors_qs}
    
    # Build list of visitors with timestamp
    visitor_list = []
    for v in recent_visitors:
        p = visitors.get(v['viewer'])
        if p:
            p.last_view_time = v['last_view']
            visitor_list.append(p)
            
    # 3. Total view count
    total_views = ProfileView.objects.filter(viewed=profile).count()
    
    return render(request, 'web/activity/dashboard.html', {
        'likers': likers,
        'visitors': visitor_list,
        'total_views': total_views,
    })
@login_required
def help_view(request):
    """FAQ and help page"""
    return render(request, 'web/help.html')


def privacy_view(request):
    """Privacy Policy page"""
    return render(request, 'web/legal/privacy.html')


def terms_view(request):
    """Terms of Service page"""
    return render(request, 'web/legal/terms.html')


def data_deletion_view(request):
    """Data Deletion Instructions page"""
    return render(request, 'web/legal/data_deletion.html')
