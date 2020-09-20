import logging
from celery import shared_task
from requests.exceptions import RequestException

from wdf.indexer import Indexer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@shared_task(
    autoretry_for=[RequestException],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 5,
    },
)
def prepare_dump(job_id):
    logger.info(f'Preparing dump for job {job_id}')

    indexer = Indexer(get_chunk_size=5000, save_chunk_size=5000)

    indexer.prepare_dump(job_id=job_id)

    logger.info(f'Dump for job {job_id} prepared, adding import task')

    import_dump.delay(job_id=job_id)


@shared_task()
def import_dump(job_id):
    logger.info(f'Importing dump for job {job_id}')

    indexer = Indexer(get_chunk_size=1000, save_chunk_size=1000)

    indexer.import_dump(job_id=job_id)

    logger.info(f'Dump for job {job_id} imported')
