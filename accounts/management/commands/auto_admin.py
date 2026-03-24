from pathlib import Path
from typing import Any

import environ
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force the creation of the admin user",
        )

    def handle(self, *args: Any, **options: Any):
        env = environ.Env()
        env_file = Path(settings.BASE_DIR) / ".env"
        if env_file.exists():
            environ.Env.read_env(str(env_file))

        force = options.get("force", False)
        User = get_user_model()
        superusers = User.objects.filter(is_superuser=True)
        if superusers.exists() and not force:
            self.stdout.write("Superuser(s) already exists")
            return
        admin_username = env("DJANGO_ADMIN_USERNAME", default="admin")
        admin_password = env("DJANGO_ADMIN_PASSWORD", default="admin")
        admin_email = env("DJANGO_ADMIN_EMAIL", default="notset@notset.com")
        admin_qs = User.objects.filter(username=admin_username)
        if admin_qs.exists() and force:
            admin_instance = admin_qs.first()
            admin_instance.set_password(admin_password)
            admin_instance.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated admin user {admin_username} with new password"
                )
            )
            return
        admin_instance = User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created admin user {admin_username} with password {admin_password}"
            )
        )