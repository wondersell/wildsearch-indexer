from django.conf import settings
from django.core.management.base import BaseCommand
from scrapinghub import ScrapinghubClient

from wdf.tasks import prepare_dump


class Command(BaseCommand):
    help = 'Adds all everything_weekly jobs to data facility'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('--tags', type=str, default='')
        parser.add_argument('--state', type=str, default='finished', required=False)

    def handle(self, *args, **options):
        client = ScrapinghubClient(settings.SH_APIKEY)

        for job in client.get_project(settings.SH_PROJECT_ID).jobs.iter(has_tag=options['tags'].split(','), state=options['state']):
            job_id = job['key']
            prepare_dump(job_id=job_id).delay()
            self.stdout.write(self.style.SUCCESS(f'Job #{job_id} added to process queue'))
