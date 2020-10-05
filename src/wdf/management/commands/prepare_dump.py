import logging
from django.core.management.base import BaseCommand

from wdf.exceptions import DumpStateError
from wdf.indexer import Indexer
from wdf.tasks import prepare_dump


class Command(BaseCommand):
    help = 'Prepares job for importing'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=str)
        parser.add_argument('--chunk_size', type=int, default=5000, required=False)
        parser.add_argument('--background', choices=['yes', 'no'], default='yes')

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        job_id = options['job_id']

        if options['background'] == 'yes':
            prepare_dump.delay(job_id=job_id)
            self.stdout.write(self.style.SUCCESS(f'Job #{job_id} added to process queue for preparing'))
        else:
            try:
                indexer = Indexer(get_chunk_size=options['chunk_size'])
                indexer.prepare_dump(job_id=options['job_id'])
            except DumpStateError as error:
                self.stdout.write(self.style.ERROR(f'Job #{job_id} processing failed: {error}'))
