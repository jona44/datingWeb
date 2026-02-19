import os

def brand_context(request):
    """
    Provide branding information to all templates.
    """
    # For web, we can use an environment variable to set the variant
    variant = os.getenv('APP_VARIANT', 'hiv_plus')
    
    if variant == 'hiv_plus':
        return {
            'app_variant': variant,
            'brand_name': 'HIV+ Community',
            'brand_primary': 'pink-600',
            'brand_primary_hover': 'pink-700',
            'brand_primary_hex': '#FF0080',
            'brand_gradient': 'from-pink-600 to-purple-800',
        }
    else:
        return {
            'app_variant': variant,
            'brand_name': 'Diverse Hearts',
            'brand_primary': 'indigo-600',
            'brand_primary_hover': 'indigo-700',
            'brand_primary_hex': '#4F46E5',
            'brand_gradient': 'from-indigo-600 to-teal-800',
        }
