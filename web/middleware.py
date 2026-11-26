import os
from django.conf import settings
from django.shortcuts import redirect


class VariantMiddleware:
    """
    Middleware that inspects the incoming request's host to determine the active app variant.
    It attaches `app_variant` to the request object so views and context processors
    can serve the correct styling and data isolation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _normalize_variant(self, variant):
        if not variant:
            return None

        value = variant.strip().lower()
        if value in {'diversehearts', 'diverse-hearts', 'general', 'lovebyte', 'love-byte'}:
            return 'general'
        if value in {'hivplus', 'hiv-plus', 'hiv_plus', 'loveplus', 'love-plus', 'getloveplus', 'getlove-plus', 'get-love-plus'}:
            return 'hiv_plus'
        return value

    def _get_variant_domains(self):
        configured = getattr(settings, 'APP_VARIANT_DOMAINS', {}) or {}
        if not isinstance(configured, dict):
            return {}

        normalized = {}
        for variant, hosts in configured.items():
            variant_name = self._normalize_variant(variant)
            if not variant_name:
                continue

            if isinstance(hosts, str):
                host_list = [hosts]
            else:
                host_list = hosts

            normalized[variant_name] = [
                host.strip().lower()
                for host in host_list
                if isinstance(host, str) and host.strip()
            ]

        return normalized

    def _variant_for_host(self, host):
        host = host.split(':', 1)[0].strip().lower()
        for variant, domains in self._get_variant_domains().items():
            for domain in domains:
                if host == domain or host.endswith(f'.{domain}'):
                    return variant
        return None

    def __call__(self, request):
        host = request.get_host().lower()

        # 1. Explicit header from native mobile clients.
        header_variant = request.headers.get('X-App-Variant', '').strip().lower()

        prefix_stripped = False
        prefix_variant = None

        # Determine if we have an explicit single-domain URL prefix
        path_info = request.path_info
        path_parts = path_info.lstrip('/').split('/', 1)
        first_segment = path_parts[0]

        if first_segment in {'hiv-plus', 'hiv_plus', 'loveplus', 'love-plus', 'getloveplus', 'getlove-plus'}:
            prefix_variant = 'hiv_plus'
            prefix_stripped = True
        elif first_segment in {'diverse-hearts', 'diversehearts', 'general', 'lovebyte', 'love-byte'}:
            prefix_variant = 'general'
            prefix_stripped = True

        if header_variant in ('hiv_plus', 'general', 'diversehearts', 'hivplus', 'hiv-plus', 'diverse-hearts', 'lovebyte', 'loveplus', 'getloveplus', 'getlove-plus'):
            # Header always wins — update session so web views stay consistent too
            request.app_variant = self._normalize_variant(header_variant)
            if hasattr(request, 'session'):
                request.session['app_variant'] = request.app_variant
        elif prefix_stripped:
            request.app_variant = prefix_variant
            # Update session so sub-requests within the same session stay on this variant
            if hasattr(request, 'session'):
                request.session['app_variant'] = request.app_variant

            # Rewrite path_info and path to strip the variant prefix
            # Example: /hiv-plus/accounts/login/ -> /accounts/login/
            # Example: /hiv-plus/ -> /
            new_path = '/' + (path_parts[1] if len(path_parts) > 1 else '')
            request.path_info = new_path
            request.path = new_path
        else:
            # No explicit signal: check domain mapping first, then session, then env fallback.
            # Domain mapping is preferred over a stale session on a single-domain deployment.
            domain_variant = self._variant_for_host(host)
            if domain_variant:
                request.app_variant = domain_variant
            elif any(marker in host for marker in ('diversehearts', 'general', 'diverse-hearts', 'lovebyte')):
                request.app_variant = 'general'
            elif any(marker in host for marker in ('hivplus', 'hiv-plus', 'loveplus', 'getloveplus')):
                request.app_variant = 'hiv_plus'
            else:
                # Fall back to session (useful for web users who navigated via prefix before)
                session_variant = request.session.get('app_variant') if hasattr(request, 'session') else None
                request.app_variant = (
                    session_variant
                    or self._normalize_variant(os.getenv('APP_VARIANT', 'hiv_plus'))
                    or 'hiv_plus'
                )

            # Persist to session only when no stronger signal exists
            if hasattr(request, 'session') and getattr(request, 'app_variant', None):
                request.session['app_variant'] = request.app_variant

        # Redirect legacy root URLs to the explicit variant prefix when appropriate.
        # Only do this if we did not just strip the prefix to avoid redirect loops.
        if not prefix_stripped and request.path == '/' and request.app_variant in {'general', 'hiv_plus'} and not self._variant_for_host(host):
            if request.app_variant == 'general':
                return redirect('/general/', permanent=False)
            return redirect('/hiv-plus/', permanent=False)

        response = self.get_response(request)
        return response
