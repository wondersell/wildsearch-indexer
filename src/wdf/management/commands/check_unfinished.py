import logging
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from django.db.models import Count, F

from wdf.models import Dump
from wdf.tasks import prune_dump


class Command(BaseCommand):
    help = 'Clears unfinished import tasks'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('--job_id', type=str, required=False)
        parser.add_argument('--older_than', type=int, required=False, default=24 * 60)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        if options['job_id']:
            unfinished = Dump.objects.annotate(versions_diff=F('items_crawled') - Count('version', distinct=True)).filter(job=options['job_id'])
        else:
            unfinished = Dump.objects.annotate(versions_diff=F('items_crawled') - Count('version', distinct=True)).filter(state_code__lt=30)

        self.stdout.write(self.style.SUCCESS(f'{unfinished.count()} unfinished dumps found'))

        for unfinished_dump in unfinished:
            self.stdout.write(self.style.SUCCESS(f'Dump {unfinished_dump.job} has {unfinished_dump.versions_diff} diff'))

            if unfinished_dump.versions_diff == 0:
                unfinished_dump.set_state(Dump.PROCESSED)

                unfinished_dump.save()

                self.stdout.write(self.style.SUCCESS(f'Dump {unfinished_dump.job} set as processed'))
            else:
                minutes_passed = abs(datetime.now(timezone.utc) - unfinished_dump.created_at).total_seconds() / 60

                if minutes_passed > options['older_than']:
                    prune_dump.delay(job_id=unfinished_dump.job)

                    self.stdout.write(self.style.SUCCESS(f'Dump {unfinished_dump.job} scheduled for prune'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'Dump {unfinished_dump.job} is fresh, skipping'))
