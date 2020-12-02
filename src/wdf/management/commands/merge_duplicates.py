import logging
from django.core.management.base import BaseCommand
from django.db import connection

from wdf.tasks import merge_duplicate


class Command(BaseCommand):
    help = 'Merge sku duplicates'  # noqa: VNE003

    def add_arguments(self, parser):
        parser.add_argument('--chunk_size', type=int, default=1000, required=False)
        parser.add_argument('--process_all', choices=['yes', 'no'], default='no')
        parser.add_argument('--offset_start', type=int, default=0)

    def handle(self, *args, **options):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

        logger = logging.getLogger('')
        logger.addHandler(console)

        with connection.cursor() as cursor:
            offset = options['offset_start']
            limit = options['chunk_size']

            self.stdout.write(self.style.SUCCESS(f'Start creating tasks for duplicates with chunk size {limit}'))

            while True:
                if options['process_all'] == 'no':
                    cursor.execute('SELECT wdf_sku.article FROM wdf_sku GROUP BY article HAVING count(wdf_sku.id) > 1 LIMIT %s OFFSET %s;', [limit, offset])
                else:
                    cursor.execute('SELECT DISTINCT wdf_sku.article FROM wdf_sku LIMIT %s OFFSET %s;', [limit, offset])

                articles = cursor.fetchall()

                for article in articles:
                    merge_duplicate.delay(sku_article=article[0])

                if len(articles) == 0:
                    self.stdout.write(self.style.SUCCESS('No more duplicates, stop producing tasks'))

                    break
                else:
                    self.stdout.write(self.style.SUCCESS(f'{len(articles)} tasks added to queue (LIMIT {limit} OFFSET {offset})'))

                offset += limit
