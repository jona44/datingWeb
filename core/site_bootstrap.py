from django.conf import settings
from django.contrib.sites.models import Site
from django.db import DatabaseError, OperationalError, connection


def ensure_default_site():
    """Create the default Site row if the sites table is present and empty."""
    try:
        if not connection.introspection.table_names():
            return
    except Exception:
        return

    try:
        Site.objects.get(pk=settings.SITE_ID)
    except Site.DoesNotExist:
        try:
            Site.objects.update_or_create(
                id=settings.SITE_ID,
                defaults={
                    'domain': 'example.com',
                    'name': 'example.com',
                },
            )
        except (OperationalError, DatabaseError):
            return
    except (OperationalError, DatabaseError):
        return
