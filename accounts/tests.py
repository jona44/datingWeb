import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import PhoneVerification, Profile, ProfilePhoto, User


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
        self.user = User.objects.create_user(phone_number='+27821111111', email='test@example.com')
        self.client.force_login(self.user)
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.profile.is_complete = True
        self.profile.save()

    def test_additional_photos_upload_edit_profile(self):
        """Test uploading additional photos via edit_profile view."""
        url = reverse('edit_profile')
        
        data = {
            'display_name': 'Test User',
            'birth_date': '1990-01-01',
            'gender': 'male',
            'residence_country': 'South Africa',
            'city': 'Johannesburg',
            'nationality': 'South Africa',
            'ethnicity': 'Zulu',
            'bio': 'Test Bio',
            'education_level': 'high_school',
            'employment_status': 'employed',
            'children_status': 'none',
            'children_count': 0,
            'hobbies': 'sports',
            'height': 180,
            'smoking': 'never',
            'drinking': 'never',
            
            # PreferenceForm data
            'min_age': 18,
            'max_age': 99,
            'interested_in': 'all',
            'pref_city': 'Johannesburg',
            'pref_ethnicity': 'any',
            'show_me': 'on',
            
            # Additional Photos
            'additional_photos': [generate_image_file('photo1.jpg'), generate_image_file('photo2.jpg')]
        }
        
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProfilePhoto.objects.filter(profile=self.profile).count(), 2)

    def test_onboarding_step4_photo_upload(self):
        """Test uploading additional photos via onboarding step 4."""
        self.profile.onboarding_step = 4
        self.profile.save()
        
        url = reverse('onboarding_step', args=[4])
        
        data = {
            'bio': 'Test Bio Step 4',
            'location': 'Test Location',
            'profile_picture': generate_image_file('main_profile.jpg'),
            'additional_photos': [generate_image_file('extra1.jpg')]
        }
        
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProfilePhoto.objects.filter(profile=self.profile).count(), 1)


class PhoneOTPAuthenticationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.test_phone = '+27821234567'

    def test_request_otp_model(self):
        """Test requesting OTP code via PhoneVerification model."""
        record, code = PhoneVerification.request_otp(self.test_phone)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertEqual(record.phone_number, self.test_phone)
        self.assertFalse(record.is_verified)

    def test_verify_otp_valid_and_invalid(self):
        """Test OTP verification success and failure."""
        record, code = PhoneVerification.request_otp(self.test_phone)

        # Invalid code
        success, msg = PhoneVerification.verify_otp(self.test_phone, '000000')
        self.assertFalse(success)

        # Valid code
        success, msg = PhoneVerification.verify_otp(self.test_phone, code)
        self.assertTrue(success)

        # Re-using already verified code should fail
        success, msg = PhoneVerification.verify_otp(self.test_phone, code)
        self.assertFalse(success)

    def test_resend_cooldown_enforced(self):
        """Test that requesting OTP twice within cooldown period raises ValidationError."""
        from django.core.exceptions import ValidationError
        PhoneVerification.request_otp(self.test_phone)
        with self.assertRaises(ValidationError):
            PhoneVerification.request_otp(self.test_phone)

    def test_web_send_and_verify_otp_views(self):
        """Test web AJAX endpoints for sending and verifying OTP."""
        # 1. Send OTP
        send_url = reverse('send_otp')
        response = self.client.post(send_url, {'phone_number': self.test_phone})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        # Retrieve the generated OTP from DB
        verification = PhoneVerification.objects.filter(phone_number=self.test_phone).first()
        self.assertIsNotNone(verification)

        # 2. Verify with wrong OTP
        verify_url = reverse('verify_otp')
        response = self.client.post(verify_url, {'phone_number': self.test_phone, 'otp': '999999'})
        self.assertEqual(response.status_code, 400)

        # Verify with fixed test code under override
        with override_settings(DEBUG=True, DEV_FIXED_OTP='123456'):
            response = self.client.post(verify_url, {'phone_number': self.test_phone, 'otp': '123456'})
            self.assertEqual(response.status_code, 200)
            verify_data = response.json()
            self.assertTrue(verify_data['success'])
            self.assertTrue(verify_data['is_new_user'])

        # User should now exist and be logged in
        user = User.objects.get(phone_number=self.test_phone)
        self.assertIsNotNone(user)

    def test_api_phone_send_and_verify_otp(self):
        """Test REST API endpoints: /api/auth/phone/send-otp/ and verify-otp/."""
        # Send OTP
        response = self.client.post(
            reverse('phone_send_otp'),
            {'phone_number': '+27839876543'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Verify OTP
        with override_settings(DEBUG=True, DEV_FIXED_OTP='654321'):
            response = self.client.post(
                reverse('phone_verify_otp'),
                {'phone_number': '+27839876543', 'otp': '654321'},
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('tokens', data)
            self.assertIn('access', data['tokens'])
            self.assertIn('refresh', data['tokens'])
            self.assertTrue(data['is_new_user'])


class AppVariantCompatibilityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='+27829999999', email='test_variant@example.com')
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
