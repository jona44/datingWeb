from django.apps import AppConfig

class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        import accounts.signals
        from core.site_bootstrap import ensure_default_site

        ensure_default_site()
