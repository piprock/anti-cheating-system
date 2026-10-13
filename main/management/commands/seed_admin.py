import os
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from main.models import UserProfile

logger = logging.getLogger(__name__)


def seed_admin_user() -> bool:
    """
    Seed or update the system administrator account from environment variables.
    Returns True if an admin user was created or updated, False otherwise.
    """
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    email = os.getenv("ADMIN_EMAIL", "admin@avatar.ai").strip()
    first_name = os.getenv("ADMIN_FIRST_NAME", "Адміністратор").strip()
    last_name = os.getenv("ADMIN_LAST_NAME", "Системи").strip()

    if not username or not password:
        logger.warning("seed_admin: ADMIN_USERNAME or ADMIN_PASSWORD not set in .env; skipping admin seeding.")
        return False

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        }
    )

    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    if email and not user.email:
        user.email = email
    if first_name and not user.first_name:
        user.first_name = first_name
    if last_name and not user.last_name:
        user.last_name = last_name
    user.save()

    # Ensure UserProfile exists with admin role
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.role != UserProfile.ROLE_ADMIN:
        profile.role = UserProfile.ROLE_ADMIN
        profile.save(update_fields=["role"])

    action = "Created" if created else "Updated"
    logger.info("seed_admin: Successfully %s admin user '%s'", action.lower(), username)
    return True


class Command(BaseCommand):
    help = "Seed administrator account from .env credentials"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Checking admin credentials from environment..."))
        success = seed_admin_user()
        username = os.getenv("ADMIN_USERNAME", "admin")
        if success:
            self.stdout.write(self.style.SUCCESS(f"Successfully seeded admin user: {username}"))
        else:
            self.stdout.write(self.style.WARNING("ADMIN_USERNAME or ADMIN_PASSWORD missing in .env."))
