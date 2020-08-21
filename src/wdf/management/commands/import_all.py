import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from scrapinghub import ScrapinghubClient

from wdf.tasks import prepare_dump


class Command(BaseCommand):
    help = 'Adds all selected by tag jobs to data facility'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('--tags', type=str, default='')
        parser.add_argument('--state', type=str, default='finished', required=False)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        client = ScrapinghubClient(settings.SH_APIKEY)

        for job in client.get_project(settings.SH_PROJECT_ID).jobs.iter(has_tag=options['tags'].split(','), state=options['state']):
            job_id = job['key']
            prepare_dump.delay(job_id=job_id)
            self.stdout.write(self.style.SUCCESS(f'Job #{job_id} added to process queue'))
