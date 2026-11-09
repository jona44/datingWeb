from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import Profile
from accounts.middleware import ProfileCompletionMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware

User = get_user_model()

class ProfileCompletionMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(phone_number='+27821111111', email='test@example.com')
        self.profile = Profile.objects.get(user=self.user)
        # Ensure profile starts incomplete
        self.profile.is_complete = False
        self.profile.onboarding_step = 1
        self.profile.save()

    def get_response(self, request):
        return None

    def test_authenticated_user_incomplete_profile_redirects(self):
        """Authenticated user with incomplete profile should be redirected to onboarding."""
        middleware = ProfileCompletionMiddleware(self.get_response)
        
        # Test a random path that is not onboarding or excluded
        request = self.factory.get('/discover/')
        request.user = self.user
        
        response = middleware(request)
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('onboarding_step', kwargs={'step': 1}))

    def test_authenticated_user_complete_profile_no_redirect(self):
        """Authenticated user with complete profile should not be redirected."""
        self.profile.is_complete = True
        self.profile.save()
        
        middleware = ProfileCompletionMiddleware(lambda r: 'success')
        
        request = self.factory.get('/discover/')
        request.user = User.objects.get(id=self.user.id)
        
        response = middleware(request)
        
        self.assertEqual(response, 'success')

    def test_unauthenticated_user_no_redirect(self):
        """Anonymous user should not be redirected."""
        from django.contrib.auth.models import AnonymousUser
        middleware = ProfileCompletionMiddleware(lambda r: 'success')
        
        request = self.factory.get('/discover/')
        request.user = AnonymousUser()
        
        response = middleware(request)
        self.assertEqual(response, 'success')

    def test_whitelisted_paths_no_redirect(self):
        """Incomplete user visiting whitelisted paths shouldn't be redirected."""
        middleware = ProfileCompletionMiddleware(lambda r: 'success')
        
        whitelisted = [
            reverse('onboarding_step', kwargs={'step': 1}),
            reverse('onboarding_step', kwargs={'step': 2}),
            reverse('logout'),
            '/static/css/style.css',
        ]
        
        for path in whitelisted:
            request = self.factory.get(path)
            request.user = self.user
            response = middleware(request)
            self.assertEqual(response, 'success', f"Failed for path: {path}")
