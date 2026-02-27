import os

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
        
        # 1. Check for explicit header sent by native mobile clients
        #    (mobile apps can't rely on hostname detection since they connect via IP)
        header_variant = request.headers.get('X-App-Variant', '').strip().lower()
        if header_variant in ('hiv_plus', 'general'):
            request.app_variant = header_variant
        # 2. Determine variant based on domain name (for web browser clients)
        elif 'diversehearts' in host or 'general' in host:
            request.app_variant = 'general'
        elif 'hivplus' in host:
            request.app_variant = 'hiv_plus'
        else:
            # 3. Fallback to default ENV if accessed via raw IP or standard localhost
            request.app_variant = os.getenv('APP_VARIANT', 'hiv_plus')

        response = self.get_response(request)
        return response
