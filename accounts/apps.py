from django.apps import AppConfig

class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        import accounts.signals
        from django.db.models.signals import post_migrate
        from core.site_bootstrap import ensure_default_site

        post_migrate.connect(
            ensure_default_site,
            sender=self,
            dispatch_uid="accounts.ensure_default_site",
        )
