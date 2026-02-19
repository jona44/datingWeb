from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .managers import UserManager
from .constants import COUNTRY_CHOICES, CITY_CHOICES, ETHNICITY_CHOICES
import uuid


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Profile(models.Model):
    # Core Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    
    # Gender & Basic Info
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),

    ]
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    
    # Location
    location = models.CharField(max_length=255, blank=True, help_text="General area")
    residence_country = models.CharField(max_length=100, choices=COUNTRY_CHOICES, blank=True)
    city = models.CharField(max_length=100, choices=CITY_CHOICES, blank=True)
    nationality = models.CharField(max_length=100, choices=COUNTRY_CHOICES, blank=True)
    
    ethnicity = models.CharField(max_length=50, choices=ETHNICITY_CHOICES, blank=True)
    
    # Personal Details
    EMPLOYMENT_CHOICES = [
        ('employed', 'Employed'),
        ('self_employed', 'Self-employed'),
        ('unemployed', 'Unemployed'),
        ('student', 'Student'),
        ('retired', 'Retired'),
        ('other', 'Other'),
    ]
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, blank=True)
    
    EDUCATION_CHOICES = [
        ('high_school', 'High School'),
        ('associate', 'Associate Degree'),
        ('bachelor', 'Bachelor\'s Degree'),
        ('master', 'Master\'s Degree'),
        ('doctorate', 'Doctorate'),
        ('other', 'Other'),
    ]
    education_level = models.CharField(max_length=20, choices=EDUCATION_CHOICES, blank=True)
    
    CHILDREN_CHOICES = [
        ('none', 'No children'),
        ('have_children', 'Have children'),
        ('want_children', 'Want children'),
        ('dont_want', 'Don\'t want children'),
        ('open', 'Open to children'),
    ]
    children_status = models.CharField(max_length=20, choices=CHILDREN_CHOICES, blank=True)
    children_count = models.IntegerField(null=True, blank=True, default=0)
    
    # Interests & Lifestyle
    HOBBY_CHOICES = [
        ('sports', 'Sports & Fitness'),
        ('travel', 'Travel & Adventure'),
        ('music', 'Music & Arts'),
        ('reading', 'Reading & Writing'),
        ('gaming', 'Gaming & Technology'),
        ('movies', 'Movies & TV'),
        ('cooking', 'Cooking & Food'),
        ('nature', 'Nature & Outdoors'),
        ('photography', 'Photography'),
        ('fashion', 'Fashion'),
    ]
    hobbies = models.CharField(max_length=255, blank=True)
    height = models.IntegerField(null=True, blank=True, help_text="Height in cm")
    
    SMOKING_CHOICES = [
        ('never', 'Never'),
        ('occasionally', 'Occasionally'),
        ('regularly', 'Regularly'),
        ('trying_to_quit', 'Trying to quit'),
    ]
    smoking = models.CharField(max_length=20, choices=SMOKING_CHOICES, blank=True)
    
    DRINKING_CHOICES = [
        ('never', 'Never'),
        ('socially', 'Socially'),
        ('regularly', 'Regularly'),
    ]
    drinking = models.CharField(max_length=20, choices=DRINKING_CHOICES, blank=True)
    
    # HIV-Specific Fields (All Optional & Sensitive)
    diagnosis_year = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Year of diagnosis (YYYY) - completely optional and private"
    )
    
    TREATMENT_CHOICES = [
        ('on_treatment', 'On treatment'),
        ('not_on_treatment', 'Not on treatment'),
        ('undetectable', 'Undetectable viral load'),
        ('prefer_not_say', 'Prefer not to say'),
    ]
    treatment_status = models.CharField(max_length=20, choices=TREATMENT_CHOICES, blank=True)
    
    support_seeking = models.BooleanField(
        default=False,
        help_text="Looking for community support"
    )
    
    DISCLOSURE_CHOICES = [
        ('very_comfortable', 'Very comfortable discussing'),
        ('somewhat_comfortable', 'Somewhat comfortable'),
        ('private', 'Keep private'),
    ]
    disclosure_comfort = models.CharField(max_length=30, choices=DISCLOSURE_CHOICES, blank=True)
    
    # Profile Status
    APP_VARIANT_CHOICES = [
        ('hiv_plus', 'HIV+ Community'),
        ('general', 'Diverse Hearts'),
    ]
    app_variant = models.CharField(
        max_length=20, 
        choices=APP_VARIANT_CHOICES, 
        default='hiv_plus',
        help_text="The app variant this profile belongs to"
    )
    is_visible = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_complete = models.BooleanField(default=False)
    onboarding_step = models.IntegerField(default=0)
    profile_completeness = models.IntegerField(default=0, help_text="Percentage 0-100")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(default=timezone.now)

    @property
    def is_online(self):
        from .presence import is_online
        return is_online(self.id)

    def __str__(self):
        return self.display_name or self.user.email
    
    def save(self, *args, **kwargs):
        # Update completeness percentage before saving
        self.profile_completeness = self.calculate_completeness()
        super().save(*args, **kwargs)

    def calculate_completeness(self):
        """Calculate profile completion percentage"""
        core_fields = [
            self.display_name, self.bio, self.birth_date, self.gender, 
            self.residence_country, self.city, self.nationality, 
            self.profile_picture, self.location
        ]
        lifestyle_fields = [
            self.education_level, self.employment_status, 
            self.children_status, self.hobbies, self.height, 
            self.smoking, self.drinking, self.ethnicity
        ]
        
        all_fields = core_fields + lifestyle_fields
        filled = sum(1 for field in all_fields if field)
        return int((filled / len(all_fields)) * 100)

    @property
    def all_photos(self):
        """Return main profile picture + additional photos"""
        photos = []
        if self.profile_picture:
            photos.append(self.profile_picture.url)
        
        additional = self.photos.all().order_by('order')
        for p in additional:
            photos.append(p.image.url)
        return photos


class ProfilePhoto(models.Model):
    """Store additional profile photos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='profile_photos/')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Photo for {self.profile.display_name}"


