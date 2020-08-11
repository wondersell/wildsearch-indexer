import logging

from django.core.management.base import BaseCommand

from wdf.indexer import Indexer


class Command(BaseCommand):
    help = 'Adds specified job to data facility'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=str)
        parser.add_argument('--chunk_size', type=int, default=500, required=False)

    def handle(self, *args, **options):
        logger = logging.getLogger('')
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(console)

        indexer = Indexer(stdout=self.stdout, style=self.style)
        indexer.process_job(job_id=options['job_id'], chunk_size=options['chunk_size'])
