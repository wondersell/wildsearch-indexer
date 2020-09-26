import logging
from django.core.management.base import BaseCommand

from wdf.indexer import Indexer
from wdf.tasks import prepare_dump


class Command(BaseCommand):
    help = 'Prepares job for importing'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=str)
        parser.add_argument('--chunk_size', type=int, default=5000, required=False)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        indexer = Indexer(get_chunk_size=options['chunk_size'])
        indexer.prepare_dump(job_id=options['job_id'])

        if options['background']:
            job_id = options['job_id']
            prepare_dump.delay(job_id=job_id)
            self.stdout.write(self.style.SUCCESS(f'Job #{job_id} added to process queue for preparing'))
        else:
            indexer = Indexer(get_chunk_size=options['chunk_size'])
            indexer.import_dump(job_id=options['job_id'])
