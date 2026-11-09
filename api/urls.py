from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import CustomTokenObtainPairSerializer
from .views import (
    BlockViewSet,
    ConversationViewSet,
    LikeViewSet,
    MatchViewSet,
    MessageViewSet,
    PreferenceViewSet,
    ProfilePhotoViewSet,
    ProfileViewSet,
    ReportViewSet,
    SkipViewSet,
    SocialLoginView,
    current_user,
    get_geographic_metadata,
    logout_user,
    phone_send_otp,
    phone_verify_otp,
    register_user,
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r'profiles', ProfileViewSet, basename='profile')
router.register(r'profile-photos', ProfilePhotoViewSet, basename='profile-photo')
router.register(r'preferences', PreferenceViewSet, basename='preference')
router.register(r'likes', LikeViewSet, basename='like')
router.register(r'matches', MatchViewSet, basename='match')
router.register(r'blocks', BlockViewSet, basename='block')
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'skips', SkipViewSet, basename='skip')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    # Phone Passwordless OTP Authentication
    path('auth/phone/send-otp/', phone_send_otp, name='phone_send_otp'),
    path('auth/phone/verify-otp/', phone_verify_otp, name='phone_verify_otp'),

    # Existing Auth routes (JWT, Social, Legacy)
    path('auth/register/', register_user, name='register'),
    path('auth/login/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair'),
    path('auth/social/', SocialLoginView.as_view(), name='social_login'),
    path('auth/token/', TokenObtainPairView.as_view(serializer_class=CustomTokenObtainPairSerializer), name='token_obtain_pair_alias'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', logout_user, name='api_logout'),
    path('auth/me/', current_user, name='current-user'),
    
    # Metadata
    path('meta/geographic/', get_geographic_metadata, name='geographic-metadata'),
    
    # ViewSet routes
    path('', include(router.urls)),
]
