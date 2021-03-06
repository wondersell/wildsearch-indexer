import environ
import logging
from celery import chain, chord
from django.conf import settings
from django.core.management.base import BaseCommand
from math import ceil
from scrapinghub import ScrapinghubClient

from wdf.indexer import Indexer
from wdf.tasks import import_dump, prepare_dump, wrap_dump

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()


class Command(BaseCommand):
    help = 'Adds all selected by tag jobs to data facility'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('--tags', type=str, default='')
        parser.add_argument('--state', type=str, default='finished', required=False)
        parser.add_argument('--chunk_size', type=int, default=env('INDEXER_GET_CHUNK_SIZE'), required=False)
        parser.add_argument('--group_size', type=int, default=env('INDEXER_GET_CHUNK_SIZE'), required=False)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        client = ScrapinghubClient(settings.SH_APIKEY)

        for job in client.get_project(settings.SH_PROJECT_ID).jobs.iter(has_tag=options['tags'].split(','), state=options['state']):
            job_id = job['key']

            indexer = Indexer(job_id=job_id)

            if indexer.dump.state_code > 25:
                self.stdout.write(self.style.SUCCESS(f'Job #{job_id} already imported'))
                continue

            group_size = options['group_size']

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

            self.stdout.write(self.style.SUCCESS(
                f'Job #{job_id} added to process queue for import ({tasks_num} tasks with up to {group_size} items each)'))
