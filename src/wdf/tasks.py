import environ
import logging
import sys
from celery import shared_task
from requests.exceptions import RequestException

from wdf.exceptions import DumpStateTooEarlyError, DumpStateTooLateError
from wdf.indexer import Indexer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()


@shared_task(
    autoretry_for=[RequestException, DumpStateTooEarlyError],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 5,
    },
)
def prepare_dump(job_id):
    logger.info(f'Preparing dump for job {job_id}')

    indexer = Indexer(get_chunk_size=env('INDEXER_GET_CHUNK_SIZE'), save_chunk_size=env('INDEXER_SAVE_CHUNK_SIZE'))

    try:
        indexer.prepare_dump(job_id=job_id)
    except DumpStateTooLateError as e:
        logger.error(f'Job {job_id} import failed. {str(e)}')
    else:
        logger.info(f'Dump for job {job_id} prepared')


@shared_task(
    autoretry_for=[DumpStateTooEarlyError],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 100,
    },
)
def import_dump(job_id, start=0, count=sys.maxsize):
    logger.info(f'Importing dump for job {job_id} from item {start}, {count} items max')

    indexer = Indexer(get_chunk_size=env('INDEXER_GET_CHUNK_SIZE'), save_chunk_size=env('INDEXER_SAVE_CHUNK_SIZE'))

    try:
        indexer.import_dump(job_id=job_id, start=start, count=count)
    except DumpStateTooLateError as e:
        logger.error(f'Job {job_id} import failed. {str(e)}')
    else:
        logger.info(f'Dump for job {job_id} imported')
