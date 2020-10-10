import logging
from django.core.management.base import BaseCommand
from django.db.models import Count, F

from wdf.models import Dump
from wdf.tasks import prune_dump


class Command(BaseCommand):
    help = 'Clears unfinished import tasks'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('--job_id', type=str, required=False)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        if options['job_id']:
            unfilled_dumps = [options['job_id']]
        else:
            unfilled_dumps = [dump.job for dump in Dump.objects.annotate(versions_diff=F('items_crawled') - Count('version', distinct=True)).filter(versions_diff__gt=0)]

        for unfilled in unfilled_dumps:
            prune_dump.delay(job_id=unfilled)

            self.stdout.write(self.style.SUCCESS(f'Dump {unfilled} scheduled for prune'))
