from django.core.management.base import BaseCommand
from django.conf import settings
from scrapinghub import ScrapinghubClient

from app.tasks import import_version


class Command(BaseCommand):
    help = 'Adds specified job to data facility'  # noqa: VNE003

    #def add_arguments(self, parser):
    #    parser.add_argument('job_tags', type=str)

    def handle(self, *args, **options):
        client = ScrapinghubClient(settings.SH_APIKEY)

        for job in client.get_project(settings.SH_PROJECT_ID).jobs.iter(has_tag=['everything_weekly']):
            job_id = job['key']
            import_version(job_id=job_id).delay()
            self.stdout.write(self.style.SUCCESS(
                f'Job #{job_id} added to process queue'))
