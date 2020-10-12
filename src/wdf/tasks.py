import environ
import logging
import sys
from celery import shared_task
from requests.exceptions import RequestException

from wdf.exceptions import DumpStateTooEarlyError, DumpStateTooLateError
from wdf.indexer import Indexer
from wdf.models import Dump

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

    indexer = Indexer(job_id=job_id)

    try:
        indexer.prepare_dump()
    except DumpStateTooLateError as e:
        logger.error(f'Job {job_id} prepare failed. {str(e)}')
    else:
        logger.info(f'Dump for job {job_id} prepared')

    return job_id


@shared_task(
    autoretry_for=[DumpStateTooEarlyError],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 100,
    },
)
def import_dump(job_id, start=0, count=sys.maxsize):
    logger.info(f'Importing dump for job {job_id} from item {start}, {count} items max')

    indexer = Indexer(job_id=job_id)

    try:
        indexer.import_dump(start=start, count=count)
    except DumpStateTooLateError as e:
        logger.error(f'Job {job_id} import failed. {str(e)}')
    else:
        logger.info(f'Dump for job {job_id} imported')

    return job_id


@shared_task(retry_kwargs={
    'max_retries': 2,
    'countdown': 100,
})
def wrap_dump(results, job_id):
    indexer = Indexer(job_id=job_id)

    try:
        indexer.wrap_dump()
    except Exception as e:
        logger.info(f'Dump for job {job_id} wrapping failed. {str(e)}')
    else:
        logger.info(f'Dump for job {job_id} wrapped up')

    return job_id


@shared_task(retry_kwargs={
    'max_retries': 10,
    'countdown': 100,
})
def prune_dump(job_id):
    dump = Dump.objects.filter(job=job_id).first()

    dump.prune()

    return True
