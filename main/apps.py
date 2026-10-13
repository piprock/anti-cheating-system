from django.apps import AppConfig
from django.db.models.signals import post_migrate
import logging

logger = logging.getLogger(__name__)


def auto_seed_admin(sender, **kwargs):
    """Auto-seed admin account immediately after migrations run."""
    try:
        from main.management.commands.seed_admin import seed_admin_user
        seed_admin_user()
    except Exception as exc:
        logger.warning("auto_seed_admin failed during post_migrate: %s", exc)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        post_migrate.connect(auto_seed_admin, sender=self)
