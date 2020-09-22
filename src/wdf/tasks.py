import logging
from celery import shared_task
from requests.exceptions import RequestException

from wdf.indexer import Indexer
from wdf.exceptions import DumpStateTooEarlyError, DumpStateTooLateError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@shared_task(
    autoretry_for=[RequestException, DumpStateTooEarlyError],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 5,
    },
)
def prepare_dump(job_id):
    logger.info(f'Preparing dump for job {job_id}')

    indexer = Indexer(get_chunk_size=5000, save_chunk_size=5000)

    try:
        indexer.prepare_dump(job_id=job_id)
    except DumpStateTooLateError as e:
        logger.error(f'Job {job_id} import failed. {e.message}')

    logger.info(f'Dump for job {job_id} prepared, adding import task')

    import_dump.delay(job_id=job_id)


@shared_task(
    autoretry_for=[DumpStateTooEarlyError],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 100,
    },
)
def import_dump(job_id):
    logger.info(f'Importing dump for job {job_id}')

    indexer = Indexer(get_chunk_size=1000, save_chunk_size=1000)

    try:
        indexer.import_dump(job_id=job_id)
    except DumpStateTooLateError as e:
        logger.error(f'Job {job_id} import failed. {e.message}')

    logger.info(f'Dump for job {job_id} imported')
