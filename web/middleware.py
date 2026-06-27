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
        if value in {'diversehearts', 'diverse-hearts', 'general'}:
            return 'general'
        if value in {'hivplus', 'hiv-plus', 'hiv_plus'}:
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
        path = request.path.lstrip('/').split('/', 1)[0]

        # 1. Explicit header from native mobile clients.
        header_variant = request.headers.get('X-App-Variant', '').strip().lower()
        if header_variant in ('hiv_plus', 'general', 'diversehearts', 'hivplus', 'hiv-plus', 'diverse-hearts'):
            request.app_variant = self._normalize_variant(header_variant)
            response = self.get_response(request)
            return response

        # 2. Explicit single-domain URL prefix.
        if path in {'hiv-plus', 'hiv_plus'}:
            request.app_variant = 'hiv_plus'
        elif path in {'diverse-hearts', 'diversehearts', 'general'}:
            request.app_variant = 'general'
        else:
            domain_variant = self._variant_for_host(host)
            if domain_variant:
                request.app_variant = domain_variant
            else:
                # 3. Determine variant based on domain name for regular browser traffic.
                if any(marker in host for marker in ('diversehearts', 'general', 'diverse-hearts')):
                    request.app_variant = 'general'
                elif any(marker in host for marker in ('hivplus', 'hiv-plus')):
                    request.app_variant = 'hiv_plus'
                else:
                    # 4. Fallback to the environment variable for raw IP / localhost / Railway.
                    request.app_variant = self._normalize_variant(os.getenv('APP_VARIANT', 'hiv_plus')) or 'hiv_plus'

        # Redirect legacy root URLs to the explicit variant prefix when appropriate.
        if request.path == '/' and request.app_variant in {'general', 'hiv_plus'} and not self._variant_for_host(host):
            if request.app_variant == 'general':
                return redirect('/general/', permanent=False)
            return redirect('/hiv-plus/', permanent=False)

        response = self.get_response(request)
        return response
