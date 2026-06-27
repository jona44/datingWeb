from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import User, Profile, ProfilePhoto
import io
from PIL import Image

def generate_image_file(name='test_image.jpg'):
    """Generate a valid image file for testing."""
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100), 'red')
    image.save(file, 'JPEG')
    file.seek(0)
    return SimpleUploadedFile(name, file.read(), content_type='image/jpeg')

class ProfilePhotoUploadTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='test@example.com', password='password123')
        self.client.login(email='test@example.com', password='password123')
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.profile.is_complete = True
        self.profile.save()

    def test_additional_photos_upload_edit_profile(self):
        """Test uploading additional photos via edit_profile view."""
        url = reverse('edit_profile')
        
        # Prepare valid form data
        data = {
            # ProfileForm data
            'display_name': 'Test User',
            'birth_date': '1990-01-01',
            'gender': 'male',
            'city': 'Test City',
            'nationality': 'Test Nation',
            'ethnicity': 'any',
            'bio': 'Test Bio',
            'education_level': 'high_school',
            'employment_status': 'employed',
            'children_status': 'none',
            'children_count': 0,
            'hobbies': 'Test Hobbies',
            'height': 180,
            'smoking': 'never',
            'drinking': 'never',
            'diagnosis_year': '',
            'treatment_status': '',
            'disclosure_comfort': '',
            
            # PreferenceForm data
            'min_age': 18,
            'max_age': 99,
            'interested_in': 'all',
            'pref_city': 'Test City',
            'pref_max_children': '',
            'pref_nationality': '',
            'pref_ethnicity': 'any',
            'show_me': 'on',
            
            # Additional Photos (manual handling)
            'additional_photos': [generate_image_file('photo1.jpg'), generate_image_file('photo2.jpg')]
        }
        
        response = self.client.post(url, data, follow=True)
        
        # Check validation success
        # Check validation success
        if response.context:
             if 'form' in response.context and response.context['form'].errors:
                 pass
             if 'pref_form' in response.context and response.context['pref_form'].errors:
                 pass

        self.assertEqual(response.status_code, 200)
        
        # Verify photos were created
        self.assertEqual(ProfilePhoto.objects.filter(profile=self.profile).count(), 2)

    def test_onboarding_step4_photo_upload(self):
        """Test uploading additional photos via onboarding step 4."""
        # Ensure we are on step 4
        self.profile.onboarding_step = 4
        self.profile.save()
        
        url = reverse('onboarding_step', args=[4])
        
        data = {
            'bio': 'Test Bio Step 4',
            'location': 'Test Location',
            # additional_photos
            'additional_photos': [generate_image_file('step4_photo.jpg')]
        }
        
        response = self.client.post(url, data, follow=True)
        
        if response.context and 'form' in response.context:
             if response.context['form'].errors:
                 print("Step 4 Form Errors:", response.context['form'].errors)

        self.assertEqual(response.status_code, 200)
        
        # Verify photo count (2 from previous test if ran sequentially? No, TestCase cleans up DB)
        # But this is a separate test method.
        self.assertEqual(ProfilePhoto.objects.filter(profile=self.profile).count(), 1)


class AppVariantCompatibilityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test_variant@example.com', password='password123')
        self.profile, _ = Profile.objects.get_or_create(user=self.user)

    def test_serializer_normalization(self):
        """Test that ProfileUpdateSerializer maps 'diversehearts' to 'general'."""
        from api.serializers import ProfileUpdateSerializer
        data = {
            'app_variant': 'diversehearts',
            'display_name': 'Test Normalization'
        }
        serializer = ProfileUpdateSerializer(instance=self.profile, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        profile = serializer.save()
        self.assertEqual(profile.app_variant, 'general')

    def test_middleware_normalization(self):
        """Test that VariantMiddleware maps X-App-Variant: diversehearts header to general."""
        from django.test import RequestFactory
        from web.middleware import VariantMiddleware
        factory = RequestFactory()
        request = factory.get('/api/profiles/me/', HTTP_X_APP_VARIANT='diversehearts')
        
        middleware = VariantMiddleware(lambda req: req)
        middleware(request)
        
        self.assertEqual(request.app_variant, 'general')

    def test_middleware_uses_configured_domain_mapping(self):
        """Test that VariantMiddleware uses configured hostnames for each variant."""
        from django.test import RequestFactory
        from web.middleware import VariantMiddleware

        factory = RequestFactory()
        request = factory.get('/', HTTP_HOST='community.example.com')

        middleware = VariantMiddleware(lambda req: req)
        with override_settings(
            APP_VARIANT_DOMAINS={
                'general': ['community.example.com'],
            }
        ):
            middleware(request)

        self.assertEqual(request.app_variant, 'general')
