import logging
from django.core.management.base import BaseCommand

from wdf.indexer import Indexer


class Command(BaseCommand):
    help = 'Prepares job for importing'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=str)
        parser.add_argument('--save_chunk_size', type=int, default=100, required=False)
        parser.add_argument('--get_chunk_size', type=int, default=100, required=False)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        indexer = Indexer(get_chunk_size=options['get_chunk_size'], save_chunk_size=options['save_chunk_size'])
        indexer.prepare_dump(job_id=options['job_id'])
