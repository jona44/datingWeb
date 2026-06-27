import os
from django.shortcuts import redirect


class VariantMiddleware:
    """
    Middleware that inspects the incoming request's host to determine the active app variant.
    It attaches `app_variant` to the request object so views and context processors
    can serve the correct styling and data isolation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().lower()
        path = request.path.lstrip('/').split('/', 1)[0]

        # 1. Explicit header from native mobile clients.
        header_variant = request.headers.get('X-App-Variant', '').strip().lower()
        if header_variant in ('hiv_plus', 'general', 'diversehearts'):
            request.app_variant = 'general' if header_variant == 'diversehearts' else header_variant
            response = self.get_response(request)
            return response

        # 2. Explicit single-domain URL prefix.
        if path in {'hiv-plus', 'hiv_plus'}:
            request.app_variant = 'hiv_plus'
        elif path in {'diverse-hearts', 'diversehearts', 'general'}:
            request.app_variant = 'general'
        else:
            # 3. Determine variant based on domain name for regular browser traffic.
            if any(marker in host for marker in ('diversehearts', 'general', 'diverse-hearts')):
                request.app_variant = 'general'
            elif any(marker in host for marker in ('hivplus', 'hiv-plus')):
                request.app_variant = 'hiv_plus'
            else:
                # 4. Fallback to the environment variable for raw IP / localhost / Railway.
                request.app_variant = os.getenv('APP_VARIANT', 'hiv_plus').strip().lower()
                if request.app_variant == 'diversehearts':
                    request.app_variant = 'general'

        # Redirect legacy root URLs to the explicit variant prefix when appropriate.
        if request.path == '/' and request.app_variant == 'general':
            return redirect('/general/', permanent=False)
        if request.path == '/' and request.app_variant == 'hiv_plus':
            return redirect('/hiv-plus/', permanent=False)

        response = self.get_response(request)
        return response
