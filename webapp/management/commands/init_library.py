from django.core.management.base import BaseCommand
from webapp.storage import library


class Command(BaseCommand):
    help = "Initialize document storage in the configured database."

    def handle(self, *args, **options):
        library().initialize()
        self.stdout.write("Document storage ready.")
