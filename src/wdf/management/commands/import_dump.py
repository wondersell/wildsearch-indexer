import logging
from django.core.management.base import BaseCommand

from wdf.indexer import Indexer
from wdf.tasks import import_dump


class Command(BaseCommand):
    help = 'Adds specified job to data facility'  # noqa: VNE003

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

        if options['background'] == 'yes':
            job_id = options['job_id']
            import_dump.delay(job_id=job_id)
            self.stdout.write(self.style.SUCCESS(f'Job #{job_id} added to process queue for import'))
        else:
            indexer = Indexer(get_chunk_size=options['chunk_size'])
            indexer.import_dump(job_id=options['job_id'])
