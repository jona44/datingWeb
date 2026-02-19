from rest_framework import serializers
from accounts.models import User, Profile, ProfilePhoto
from discovery.models import Preference
from interactions.models import Like, Match, Block, Report, Skip, ProfileView
from messaging.models import Conversation, Message, MessageRead
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


# ==================== ACCOUNTS SERIALIZERS ====================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom Serializer to handle both 'username' and 'email' fields in the request.
    The User model uses 'email' as the unique identifier instead of 'username'.
    """
    # Accept both 'username' and 'email' keys from clients
    username = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the requirement optional for the main identifier field (e.g. 'email')
        # because we might provide 'username' instead, which we map in validate()
        if self.username_field in self.fields:
            self.fields[self.username_field].required = False

    def validate(self, attrs):
        # The parent TokenObtainPairSerializer uses self.username_field to find the identifier.
        # For our User model, self.username_field is 'email'.
        
        # Determine the identifier from provided fields
        username_val = attrs.get('username')
        email_val = attrs.get('email')
        
        # Prefer 'email' if provided, then 'username'
        identifier = email_val or username_val
        
        if identifier:
            # Map the identifier to the field the parent serializer expects ('email')
            attrs[self.username_field] = identifier
            
            # Also ensure 'username' key exists in attrs if parent expects it (usually not if USERNAME_FIELD is email)
            # but some versions of SimpleJWT might still look for 'username' in attrs
            if 'username' not in attrs:
                 attrs['username'] = identifier
        
        try:
            return super().validate(attrs)
        except Exception as e:
            # Only print error in development for debugging
            from django.conf import settings
            if settings.DEBUG:
                print(f"Login failure for identifier '{identifier}': {str(e)}")
            raise e






class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'email', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = ['email', 'password', 'password2']
        
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        return attrs
        
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class ProfilePhotoSerializer(serializers.ModelSerializer):
    """Serializer for additional profile photos"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProfilePhoto
        fields = ['id', 'image', 'image_url', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']
        
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ProfileListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for profile lists/discovery"""
    profile_picture_url = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'id', 'display_name', 'bio', 'age', 'gender',
            'profile_picture_url', 'city', 'nationality',
            'height', 'ethnicity', 'is_verified', 'last_seen', 'is_online',
            'smoking', 'drinking'
        ]
        
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None
        
    def get_age(self, obj):
        if obj.birth_date:
            from datetime import date
            today = date.today()
            return today.year - obj.birth_date.year - (
                (today.month, today.day) < (obj.birth_date.month, obj.birth_date.day)
            )
        return None


class ProfileDetailSerializer(serializers.ModelSerializer):
    """Complete profile serializer with all details"""
    user = UserSerializer(read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    photos = ProfilePhotoSerializer(many=True, read_only=True)
    all_photo_urls = serializers.SerializerMethodField()
    matches_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'display_name', 'bio', 'birth_date', 'age',
            'profile_picture', 'profile_picture_url', 'gender',
            'location', 'residence_country', 'city', 'nationality', 'ethnicity',
            'employment_status', 'education_level',
            'children_status', 'children_count',
            'hobbies', 'height', 'smoking', 'drinking',
            'diagnosis_year', 'treatment_status', 'support_seeking',
            'disclosure_comfort', 'app_variant', 'is_visible', 'is_verified',
            'is_complete', 'onboarding_step', 'profile_completeness',
            'photos', 'all_photo_urls', 'created_at', 'last_seen',
            'matches_count'
        ]
        read_only_fields = [
            'id', 'user', 'is_verified', 'is_complete',
            'profile_completeness', 'created_at', 'last_seen',
            'matches_count'
        ]
        
    def get_matches_count(self, obj):
        return obj.matches_as_profile1.count() + obj.matches_as_profile2.count()
        
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None
        
    def get_age(self, obj):
        if obj.birth_date:
            from datetime import date
            today = date.today()
            return today.year - obj.birth_date.year - (
                (today.month, today.day) < (obj.birth_date.month, obj.birth_date.day)
            )
        return None
        
    def get_all_photo_urls(self, obj):
        request = self.context.get('request')
        urls = []
        
        if obj.profile_picture:
            if request:
                urls.append(request.build_absolute_uri(obj.profile_picture.url))
            else:
                urls.append(obj.profile_picture.url)
        
        for photo in obj.photos.all().order_by('order'):
            if request:
                urls.append(request.build_absolute_uri(photo.image.url))
            else:
                urls.append(photo.image.url)
                
        return urls


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating profile"""
    class Meta:
        model = Profile
        fields = [
            'display_name', 'bio', 'birth_date',
            'profile_picture', 'gender', 'location', 'residence_country', 'city',
            'nationality', 'ethnicity', 'employment_status',
            'education_level', 'children_status', 'children_count',
            'hobbies', 'height', 'smoking', 'drinking',
            'diagnosis_year', 'treatment_status', 'support_seeking',
            'disclosure_comfort', 'app_variant', 'is_visible', 'onboarding_step', 'is_complete'
        ]


# ==================== DISCOVERY SERIALIZERS ====================

class PreferenceSerializer(serializers.ModelSerializer):
    """Serializer for user preferences"""
    class Meta:
        model = Preference
        fields = [
            'id', 'min_age', 'max_age', 'interested_in',
            'pref_city', 'pref_residence_country', 'pref_max_children', 'pref_nationality',
            'pref_ethnicity', 'show_me', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ==================== INTERACTIONS SERIALIZERS ====================

class LikeSerializer(serializers.ModelSerializer):
    """Serializer for likes"""
    from_profile = ProfileListSerializer(read_only=True)
    to_profile = ProfileListSerializer(read_only=True)
    to_profile_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Like
        fields = ['id', 'from_profile', 'to_profile', 'to_profile_id', 'created_at']
        read_only_fields = ['id', 'from_profile', 'created_at']
        
    def create(self, validated_data):
        # from_profile is set in the view
        return super().create(validated_data)


class MatchSerializer(serializers.ModelSerializer):
    """Serializer for matches"""
    profile1 = ProfileListSerializer(read_only=True)
    profile2 = ProfileListSerializer(read_only=True)
    other_profile = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Match
        fields = ['id', 'profile1', 'profile2', 'other_profile', 'conversation_id', 'created_at']
        read_only_fields = ['id', 'profile1', 'profile2', 'created_at']
        
    def get_conversation_id(self, obj):
        from messaging.models import Conversation
        conversation = Conversation.objects.filter(
            participants=obj.profile1
        ).filter(
            participants=obj.profile2
        ).first()
        return str(conversation.id) if conversation else None
        
    def get_other_profile(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'profile'):
            current_profile = request.user.profile
            other = obj.other_profile(current_profile)
            return ProfileListSerializer(other, context=self.context).data
        return None


class BlockSerializer(serializers.ModelSerializer):
    """Serializer for blocks"""
    blocked_profile_id = serializers.UUIDField(write_only=True)
    blocked = ProfileListSerializer(read_only=True)
    
    class Meta:
        model = Block
        fields = ['id', 'blocked', 'blocked_profile_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for reports"""
    reported_profile_id = serializers.UUIDField(write_only=True)
    reported = ProfileListSerializer(read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id', 'reported', 'reported_profile_id', 'reason',
            'description', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']


class SkipSerializer(serializers.ModelSerializer):
    """Serializer for skips"""
    to_profile_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Skip
        fields = ['id', 'to_profile_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProfileViewSerializer(serializers.ModelSerializer):
    """Serializer for profile views"""
    viewed_profile_id = serializers.UUIDField(write_only=True)
    viewer = ProfileListSerializer(read_only=True)
    viewed = ProfileListSerializer(read_only=True)
    
    class Meta:
        model = ProfileView
        fields = ['id', 'viewer', 'viewed', 'viewed_profile_id', 'created_at']
        read_only_fields = ['id', 'viewer', 'created_at']


# ==================== MESSAGING SERIALIZERS ====================

class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages"""
    sender = ProfileListSerializer(read_only=True)
    sender_id = serializers.UUIDField(source='sender.id', read_only=True)
    is_read = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'sender_id', 'body', 'is_read', 'created_at']
        read_only_fields = ['id', 'sender', 'created_at']
        
    def get_is_read(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'profile'):
            return MessageRead.objects.filter(
                message=obj,
                profile=request.user.profile
            ).exists()
        return False


class ConversationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for conversation lists"""
    participants = ProfileListSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'participants', 'other_participant',
            'last_message', 'unread_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
        
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'id': str(last_msg.id),
                'body': last_msg.body,
                'created_at': last_msg.created_at,
                'sender_id': str(last_msg.sender.id)
            }
        return None
        
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'profile'):
            profile = request.user.profile
            unread = obj.messages.exclude(sender=profile).exclude(
                reads__profile=profile
            ).count()
            return unread
        return 0
        
    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'profile'):
            current_profile = request.user.profile
            other = obj.participants.exclude(id=current_profile.id).first()
            if other:
                return ProfileListSerializer(other, context=self.context).data
        return None


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Detailed conversation serializer with messages"""
    participants = ProfileListSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    other_participant = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'participants', 'other_participant',
            'messages', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
        
    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'profile'):
            current_profile = request.user.profile
            other = obj.participants.exclude(id=current_profile.id).first()
            if other:
                return ProfileListSerializer(other, context=self.context).data
        return None


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating messages"""
    class Meta:
        model = Message
        fields = ['conversation', 'body']
        
    def create(self, validated_data):
        # sender is set in the view
        return super().create(validated_data)
