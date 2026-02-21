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
        
        # Determine variant based on domain name
        # We check for 'diversehearts' or a specific local testing domain configured for it.
        # Fallback to the environment variable or 'hiv_plus' otherwise.
        
        if 'diversehearts' in host or 'general' in host:
            request.app_variant = 'general'
        elif 'hivplus' in host:
            request.app_variant = 'hiv_plus'
        else:
            # Fallback to default ENV if accessed via raw IP or standard localhost
            request.app_variant = os.getenv('APP_VARIANT', 'hiv_plus')

        response = self.get_response(request)
        return response
