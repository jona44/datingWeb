from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404
from datetime import date, datetime, timedelta
import requests

from accounts.models import User, Profile, ProfilePhoto
from discovery.models import Preference
from interactions.models import Like, Match, Block, Report, Skip, ProfileView
from messaging.models import Conversation, Message, MessageRead

from .serializers import (
    UserSerializer, UserRegistrationSerializer,
    ProfileListSerializer, ProfileDetailSerializer, ProfileUpdateSerializer,
    ProfilePhotoSerializer, PreferenceSerializer,
    LikeSerializer, MatchSerializer, BlockSerializer, ReportSerializer,
    SkipSerializer, ProfileViewSerializer,
    ConversationListSerializer, ConversationDetailSerializer,
    MessageSerializer, MessageCreateSerializer
)

from accounts.constants import GEOGRAPHIC_DATA, COUNTRY_CHOICES, ETHNICITY_CHOICES


@api_view(['GET'])
@permission_classes([AllowAny])
def get_geographic_metadata(request):
    """
    Returns structured data for countries, cities, and ethnicities
    to drive dynamic UI logic.
    """
    return Response({
        'countries': [c[0] for c in COUNTRY_CHOICES if c[0]],
        'geographic_data': GEOGRAPHIC_DATA,
        'base_ethnicities': [
            {'value': 'white', 'label': 'White / Caucasian'},
            {'value': 'black', 'label': 'Black'},
            {'value': 'colored', 'label': 'Colored'},
            {'value': 'indian', 'label': 'Indian'},
            {'value': 'asian', 'label': 'Asian'},
        ]
    })


# ==================== AUTHENTICATION VIEWS ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user"""
    serializer = UserRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        print(f"Registration validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    user = serializer.save()
    
    # Create refresh and access tokens
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'user': UserSerializer(user).data,
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """Logout user by blacklisting refresh token"""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Get current authenticated user"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class SocialLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        provider = request.data.get('provider')
        token = request.data.get('access_token')
        
        if not provider or not token:
            return Response({'error': 'Provider and token required'}, status=status.HTTP_400_BAD_REQUEST)
            
        email = None
        social_id = None
        first_name = ''
        last_name = ''
        
        try:
            if provider == 'google':
                # Verify with Google
                resp = requests.get(f'https://www.googleapis.com/oauth2/v3/userinfo?access_token={token}')
                if resp.status_code != 200:
                    return Response({'error': 'Invalid Google token'}, status=status.HTTP_400_BAD_REQUEST)
                data = resp.json()
                email = data.get('email')
                first_name = data.get('given_name', '')
                last_name = data.get('family_name', '')
                
            elif provider == 'facebook':
                # Verify with Facebook
                resp = requests.get(f'https://graph.facebook.com/me?fields=id,email,first_name,last_name&access_token={token}')
                if resp.status_code != 200:
                    return Response({'error': 'Invalid Facebook token'}, status=status.HTTP_400_BAD_REQUEST)
                data = resp.json()
                email = data.get('email')
                first_name = data.get('first_name', '')
                last_name = data.get('last_name', '')
                
            else:
                return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
                
            if not email:
                return Response({'error': 'Email not found in social account'}, status=status.HTTP_400_BAD_REQUEST)
                
            # Get or create user
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=email, 
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )
                user.set_unusable_password()
                user.save()
                
                # Create profile if not exists
                Profile.objects.get_or_create(user=user, defaults={'display_name': first_name or email.split('@')[0]})

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== PROFILE VIEWS ====================

class ProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user profiles
    
    list: Get all visible profiles (discovery)
    retrieve: Get a specific profile by ID
    update: Update current user's profile
    me: Get current user's profile
    """
    permission_classes = [IsAuthenticated]
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['gender', 'residence_country', 'city', 'nationality', 'ethnicity']
    search_fields = ['display_name', 'bio', 'hobbies']
    ordering_fields = ['created_at', 'last_seen']
    
    def get_queryset(self):
        """Filter profiles based on user preferences and blocks"""
        user = self.request.user
        
        if not hasattr(user, 'profile'):
            return Profile.objects.none()
            
        current_profile = user.profile
        
        # Base queryset - visible profiles except current user
        queryset = Profile.objects.filter(
            is_visible=True
        ).exclude(
            id=current_profile.id
        ).select_related('user').prefetch_related('photos')
        
        # Exclude blocked users (both ways)
        blocked_ids = Block.objects.filter(
            Q(blocker=current_profile) | Q(blocked=current_profile)
        ).values_list('blocked_id', 'blocker_id')
        
        blocked_profile_ids = set()
        for blocker_id, blocked_id in blocked_ids:
            blocked_profile_ids.add(blocker_id)
            blocked_profile_ids.add(blocked_id)
        
        queryset = queryset.exclude(id__in=blocked_profile_ids)
        
        # Only apply restrictive discovery filters for 'discovery' and 'list' actions
        # This prevents 404s when retrieving a specific profile that doesn't match current discovery prefs
        if self.action in ['discovery', 'list']:
            # Filter by app variant to keep communities separate in discovery
            if current_profile.app_variant:
                queryset = queryset.filter(app_variant=current_profile.app_variant)

            # Apply preferences if they exist
            if hasattr(current_profile, 'preferences'):
                prefs = current_profile.preferences
                
                # Age filter
                if prefs.min_age and prefs.max_age:
                    today = date.today()
                    min_birth_date = today.replace(year=today.year - prefs.max_age)
                    max_birth_date = today.replace(year=today.year - prefs.min_age)
                    queryset = queryset.filter(
                        birth_date__range=[min_birth_date, max_birth_date]
                    )
                
                # Gender filter
                if prefs.interested_in and prefs.interested_in != 'all':
                    queryset = queryset.filter(gender=prefs.interested_in)
                
                # City filter
                if prefs.pref_city:
                    queryset = queryset.filter(city=prefs.pref_city)
                
                # Residence Country filter
                if prefs.pref_residence_country:
                    queryset = queryset.filter(residence_country=prefs.pref_residence_country)
                
                # Nationality filter
                if prefs.pref_nationality:
                    queryset = queryset.filter(nationality=prefs.pref_nationality)
                
                # Ethnicity filter
                if prefs.pref_ethnicity and prefs.pref_ethnicity != 'any':
                    queryset = queryset.filter(ethnicity=prefs.pref_ethnicity)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProfileListSerializer
        elif self.action in ['update', 'partial_update']:
            return ProfileUpdateSerializer
        return ProfileDetailSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Get profile and record view"""
        instance = self.get_object()
        
        # Record profile view
        if hasattr(request.user, 'profile'):
            ProfileView.objects.get_or_create(
                viewer=request.user.profile,
                viewed=instance
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        """Only allow users to update their own profile"""
        if not hasattr(request.user, 'profile'):
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Ensure user can only update their own profile
        instance = request.user.profile
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return full profile detail
        return Response(
            ProfileDetailSerializer(instance, context={'request': request}).data
        )
    
    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        """Get or update current user's profile"""
        if not hasattr(request.user, 'profile'):
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        instance = request.user.profile
        
        if request.method == 'PATCH':
            serializer = ProfileUpdateSerializer(instance, data=request.data, partial=True)
            if not serializer.is_valid():
                print(f"Profile update error: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            return Response(ProfileDetailSerializer(instance, context={'request': request}).data)
            
        serializer = ProfileDetailSerializer(
            instance,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def discovery(self, request):
        """
        Get profiles for discovery feed
        Excludes liked and skipped profiles
        """
        queryset = self.get_queryset()
        current_profile = request.user.profile
        
        # Exclude already liked profiles
        liked_ids = Like.objects.filter(
            from_profile=current_profile
        ).values_list('to_profile_id', flat=True)
        queryset = queryset.exclude(id__in=liked_ids)
        
        # Exclude skipped profiles (optional: could add time-based reset)
        skipped_ids = Skip.objects.filter(
            from_profile=current_profile
        ).values_list('to_profile_id', flat=True)
        queryset = queryset.exclude(id__in=skipped_ids)
        
        # Order by recent activity
        queryset = queryset.order_by('-last_seen')
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProfileListSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        
        serializer = ProfileListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def who_liked_me(self, request):
        """Get profiles that liked current user"""
        current_profile = request.user.profile
        
        liked_by = Like.objects.filter(
            to_profile=current_profile
        ).select_related('from_profile').order_by('-created_at')
        
        profiles = [like.from_profile for like in liked_by]
        serializer = ProfileListSerializer(
            profiles,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def who_viewed_me(self, request):
        """Get profiles that viewed current user"""
        current_profile = request.user.profile
        
        # Get unique viewers
        views = ProfileView.objects.filter(
            viewed=current_profile
        ).select_related('viewer').order_by('-created_at')
        
        # Get unique profiles (latest view only)
        seen_ids = set()
        unique_profiles = []
        for view in views:
            if view.viewer.id not in seen_ids:
                unique_profiles.append(view.viewer)
                seen_ids.add(view.viewer.id)
        
        serializer = ProfileListSerializer(
            unique_profiles,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class ProfilePhotoViewSet(viewsets.ModelViewSet):
    """ViewSet for managing profile photos"""
    permission_classes = [IsAuthenticated]
    serializer_class = ProfilePhotoSerializer
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profile'):
            return ProfilePhoto.objects.filter(
                profile=self.request.user.profile
            ).order_by('order')
        return ProfilePhoto.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


# ==================== DISCOVERY/PREFERENCE VIEWS ====================

class PreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet for user preferences"""
    permission_classes = [IsAuthenticated]
    serializer_class = PreferenceSerializer
    http_method_names = ['get', 'put', 'patch']
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profile'):
            return Preference.objects.filter(profile=self.request.user.profile)
        return Preference.objects.none()
    
    def get_object(self):
        """Get or create preference for current user"""
        if hasattr(self.request.user, 'profile'):
            obj, created = Preference.objects.get_or_create(
                profile=self.request.user.profile
            )
            return obj
        return None
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's preferences"""
        obj = self.get_object()
        if obj:
            serializer = self.get_serializer(obj)
            return Response(serializer.data)
        return Response(
            {'detail': 'Preferences not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


# ==================== INTERACTION VIEWS ====================

class LikeViewSet(viewsets.ModelViewSet):
    """ViewSet for likes"""
    permission_classes = [IsAuthenticated]
    serializer_class = LikeSerializer
    http_method_names = ['get', 'post', 'delete']
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profile'):
            return Like.objects.filter(
                from_profile=self.request.user.profile
            ).select_related('from_profile', 'to_profile')
        return Like.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a like and check for match"""
        if not hasattr(request.user, 'profile'):
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        current_profile = request.user.profile
        to_profile_id = request.data.get('to_profile_id')
        
        if not to_profile_id:
            return Response(
                {'detail': 'to_profile_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            to_profile = Profile.objects.get(id=to_profile_id)
        except Profile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already liked
        like, created = Like.objects.get_or_create(
            from_profile=current_profile,
            to_profile=to_profile
        )
        
        # Check for mutual like (match)
        mutual_like = Like.objects.filter(
            from_profile=to_profile,
            to_profile=current_profile
        ).exists()
        
        is_match = False
        match_obj = None
        
        if mutual_like:
            # Create match - Ensure consistent ordering (profile1 < profile2)
            p1, p2 = sorted([current_profile, to_profile], key=lambda p: p.id)
            
            match_obj, match_created = Match.objects.get_or_create(
                profile1=p1,
                profile2=p2
            )
            
            is_match = True
            
            # Find or create conversation
            conversation = Conversation.objects.filter(
                participants=p1
            ).filter(
                participants=p2
            ).first()
            
            if not conversation:
                conversation = Conversation.objects.create()
                conversation.participants.add(p1, p2)
            
            conversation_id = str(conversation.id)
        else:
            conversation_id = None
        
        response_data = {
            'like': LikeSerializer(like, context={'request': request}).data,
            'is_match': is_match,
            'created': created,
            'match_id': str(match_obj.id) if match_obj else None,
            'conversation_id': conversation_id
        }
        
        if is_match and match_obj:
            response_data['match'] = MatchSerializer(
                match_obj,
                context={'request': request}
            ).data
        
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def received(self, request):
        """Get likes received by the current user"""
        if not hasattr(request.user, 'profile'):
            return Response([])
        
        likes = Like.objects.filter(
            to_profile=request.user.profile
        ).select_related('from_profile', 'to_profile').order_by('-created_at')
        
        serializer = LikeSerializer(likes, many=True, context={'request': request})
        return Response(serializer.data)


class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for matches"""
    permission_classes = [IsAuthenticated]
    serializer_class = MatchSerializer
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profile'):
            current_profile = self.request.user.profile
            return Match.objects.filter(
                Q(profile1=current_profile) | Q(profile2=current_profile)
            ).select_related('profile1', 'profile2').order_by('-created_at')
        return Match.objects.none()


class BlockViewSet(viewsets.ModelViewSet):
    """ViewSet for blocking users"""
    permission_classes = [IsAuthenticated]
    serializer_class = BlockSerializer
    http_method_names = ['get', 'post', 'delete']
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profile'):
            return Block.objects.filter(
                blocker=self.request.user.profile
            ).select_related('blocker', 'blocked')
        return Block.objects.none()
    
    def perform_create(self, serializer):
        blocked_profile_id = self.request.data.get('blocked_profile_id')
        try:
            blocked_profile = Profile.objects.get(id=blocked_profile_id)
            serializer.save(
                blocker=self.request.user.profile,
                blocked=blocked_profile
            )
        except Profile.DoesNotExist:
            raise serializers.ValidationError({'detail': 'Profile not found.'})


class ReportViewSet(viewsets.ModelViewSet):
    """ViewSet for reporting users"""
    permission_classes = [IsAuthenticated]
    serializer_class = ReportSerializer
    http_method_names = ['get', 'post']
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profile'):
            return Report.objects.filter(
                reporter=self.request.user.profile
            ).select_related('reporter', 'reported')
        return Report.objects.none()
    
    def perform_create(self, serializer):
        reported_profile_id = self.request.data.get('reported_profile_id')
        try:
            reported_profile = Profile.objects.get(id=reported_profile_id)
            serializer.save(
                reporter=self.request.user.profile,
                reported=reported_profile
            )
        except Profile.DoesNotExist:
            raise serializers.ValidationError({'detail': 'Profile not found.'})


class SkipViewSet(viewsets.ModelViewSet):
    """ViewSet for skipping profiles"""
    permission_classes = [IsAuthenticated]
    serializer_class = SkipSerializer
    http_method_names = ['post']
    
    def create(self, request, *args, **kwargs):
        if not hasattr(request.user, 'profile'):
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        to_profile_id = request.data.get('to_profile_id')
        
        try:
            to_profile = Profile.objects.get(id=to_profile_id)
        except Profile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        skip, created = Skip.objects.get_or_create(
            from_profile=request.user.profile,
            to_profile=to_profile
        )
        
        serializer = self.get_serializer(skip)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==================== MESSAGING VIEWS ====================

class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet for conversations"""
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post']
    
    def get_queryset(self):
        if hasattr(self.request.user, 'profile'):
            return Conversation.objects.filter(
                participants=self.request.user.profile
            ).prefetch_related('participants', 'messages').order_by('-created_at')
        return Conversation.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationDetailSerializer
    
    def retrieve(self, request, *args, **kwargs):
        """Get conversation and mark messages as read"""
        instance = self.get_object()
        
        # Mark all messages in this conversation as read
        if hasattr(request.user, 'profile'):
            unread_messages = instance.messages.exclude(
                sender=request.user.profile
            ).exclude(
                reads__profile=request.user.profile
            )
            
            for message in unread_messages:
                MessageRead.objects.get_or_create(
                    message=message,
                    profile=request.user.profile
                )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Create a new conversation with another user"""
        if not hasattr(request.user, 'profile'):
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        other_profile_id = request.data.get('participant_id')
        
        if not other_profile_id:
            return Response(
                {'detail': 'participant_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            other_profile = Profile.objects.get(id=other_profile_id)
        except Profile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if conversation already exists
        existing = Conversation.objects.filter(
            participants=request.user.profile
        ).filter(
            participants=other_profile
        ).first()
        
        if existing:
            serializer = ConversationDetailSerializer(
                existing,
                context={'request': request}
            )
            return Response(serializer.data)
        
        # Create new conversation
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user.profile, other_profile)
        
        serializer = ConversationDetailSerializer(
            conversation,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MessageViewSet(viewsets.ModelViewSet):
    """ViewSet for messages"""
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post']
    
    def get_queryset(self):
        conversation_id = self.request.query_params.get('conversation_id')
        
        if conversation_id and hasattr(self.request.user, 'profile'):
            # Verify user is participant
            conversation = get_object_or_404(
                Conversation,
                id=conversation_id,
                participants=self.request.user.profile
            )
            return Message.objects.filter(
                conversation=conversation
            ).select_related('sender').order_by('created_at')
        
        return Message.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MessageCreateSerializer
        return MessageSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new message"""
        if not hasattr(request.user, 'profile'):
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verify user is participant in conversation
        conversation = serializer.validated_data['conversation']
        if request.user.profile not in conversation.participants.all():
            return Response(
                {'detail': 'You are not a participant in this conversation.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Save with sender
        message = serializer.save(sender=request.user.profile)
        
        # Return full message data
        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a message as read"""
        message = self.get_object()
        
        if hasattr(request.user, 'profile'):
            MessageRead.objects.get_or_create(
                message=message,
                profile=request.user.profile
            )
            return Response({'detail': 'Message marked as read.'})
        
        return Response(
            {'detail': 'Profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
