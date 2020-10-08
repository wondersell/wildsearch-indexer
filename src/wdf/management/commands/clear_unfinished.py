import logging
from django.core.management.base import BaseCommand
from django.db.models import Count, F

from wdf.models import Dump


class Command(BaseCommand):
    help = 'Clears unfinished import tasks'  # noqa: VNE003

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        unfilled_dumps = Dump.objects.annotate(num_versions=Count('version', distinct=True), versions_diff=F('items_crawled') - Count('version', distinct=True)).filter(versions_diff__gte=0).order_by('job')

        for unfilled in unfilled_dumps:
            self.stdout.write(self.style.SUCCESS(f'Dump {unfilled.job} unfilled: {unfilled.num_versions} versions instead of {unfilled.items_crawled} ({unfilled.versions_diff} diff), deleting'))

            deleted = unfilled.delete()

            self.stdout.write(self.style.SUCCESS(
                f'Deleted {deleted[0]} objects: {deleted[1]}'))
