from django.db import models
from accounts.constants import COUNTRY_CHOICES, CITY_CHOICES, ETHNICITY_CHOICES as BASE_ETHNICITY_CHOICES

# Filter out the empty choice from base and add 'any'
ETHNICITY_CHOICES = [('any', 'Any')] + [c for c in BASE_ETHNICITY_CHOICES if c[0]]


class Preference(models.Model):
    """Store user's discovery preferences and search criteria"""
    profile = models.OneToOneField('accounts.Profile', on_delete=models.CASCADE, related_name='preferences')
    
    # Age preferences
    min_age = models.IntegerField(default=18)
    max_age = models.IntegerField(default=99)
    
    # Gender preferences
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('all', 'All'),
    ]
    interested_in = models.CharField(max_length=10, choices=GENDER_CHOICES, default='all')
    
    # Location preferences
    pref_city = models.CharField(max_length=100, choices=CITY_CHOICES, blank=True, help_text="Preferred city")
    pref_residence_country = models.CharField(max_length=100, choices=COUNTRY_CHOICES, blank=True, help_text="Preferred country of residence")
    
    # Lifestyle preferences
    pref_max_children = models.IntegerField(null=True, blank=True, help_text="Maximum number of children a partner has")
    pref_nationality = models.CharField(max_length=100, choices=COUNTRY_CHOICES, blank=True, help_text="Preferred nationality")
    
    pref_ethnicity = models.CharField(max_length=100, choices=ETHNICITY_CHOICES, default='any')
    
    # Visibility
    show_me = models.BooleanField(default=True, help_text="Show my profile in discovery")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.profile.display_name}"
