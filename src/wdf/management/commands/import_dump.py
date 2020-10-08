import logging
from celery import group
from django.core.management.base import BaseCommand
from math import ceil

from wdf.exceptions import DumpStateError
from wdf.indexer import Indexer
from wdf.models import Dump
from wdf.tasks import import_dump


class Command(BaseCommand):
    help = 'Adds specified job to data facility'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=str)
        parser.add_argument('--chunk_size', type=int, default=5000, required=False)
        parser.add_argument('--group_size', type=int, default=300000, required=False)
        parser.add_argument('--background', choices=['yes', 'no'], default='yes')

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        job_id = options['job_id']
        group_size = options['group_size']

        if options['background'] == 'yes':
            dump = Dump.objects.filter(job=job_id).first()
            tasks = ceil(dump.items_crawled / group_size)

            group(import_dump.s(job_id=job_id, start=group_size * i, count=group_size) for i in range(tasks)).apply_async(expires=24 * 60 * 60)

            self.stdout.write(self.style.SUCCESS(f'Job #{job_id} added to process queue for import ({tasks} tasks with up to {group_size} items each)'))
        else:
            try:
                indexer = Indexer(get_chunk_size=options['chunk_size'])
                indexer.import_dump(job_id=options['job_id'])
            except DumpStateError as error:
                self.stdout.write(self.style.ERROR(f'Job #{job_id} processing failed: {error}'))
