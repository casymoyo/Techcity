from django.core.management import BaseCommand
from finance.scheduler import scheduler

class Command(BaseCommand):
    def handle(self, *args, **options):
        scheduler.run()