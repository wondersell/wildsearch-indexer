import logging
from celery import chain, chord
from django.core.management.base import BaseCommand
from math import ceil

from wdf.indexer import Indexer
from wdf.tasks import import_dump, prepare_dump, wrap_dump


class Command(BaseCommand):
    help = 'Adds specified job to data facility'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=str)
        parser.add_argument('--chunk_size', type=int, default=5000, required=False)
        parser.add_argument('--group_size', type=int, default=5000, required=False)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        job_id = options['job_id']
        group_size = options['group_size']

        indexer = Indexer(job_id=job_id)

        if options['chunk_size']:
            indexer.set_chunk_size_get(options['chunk_size'])
            indexer.set_chunk_size_save(options['chunk_size'])

        tasks_num = ceil(indexer.dump.items_crawled / group_size)

        chain(
            prepare_dump.s(job_id=job_id),
            chord(
                [import_dump.s(job_id=job_id, start=group_size * i, count=group_size) for i in range(tasks_num)],
                wrap_dump.s(job_id=job_id),
            ),
        ).apply_async(expires=24 * 60 * 60)

        self.stdout.write(self.style.SUCCESS(f'Job #{job_id} added to process queue for import ({tasks_num * 2} tasks with up to {group_size} items each)'))
