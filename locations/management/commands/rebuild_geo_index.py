from django.core.management.base import BaseCommand

from locations.services import rebuild_property_index


class Command(BaseCommand):
    help = "Rebuild the Redis GEO index of active properties"

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS(f"Indexed {rebuild_property_index()} properties"))
