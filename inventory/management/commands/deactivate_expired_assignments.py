from django.core.management.base import BaseCommand

from inventory.services import deactivate_expired_assignments


class Command(BaseCommand):
    help = (
        "Deactivate therapist supply assignments whose age exceeds "
        "(item.assignment_inactive_after_days * quantity_assigned)."
    )

    def handle(self, *args, **options):
        updated = deactivate_expired_assignments()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deactivation completed. Updated assignments: {updated}."
            )
        )
