from requests.exceptions import RequestException

from app.celery import celery
from wdf.indexer import Indexer


@celery.task(
    autoretry_for=[RequestException],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 5,
    },
)
def import_version(job_id):
    indexer = Indexer()
    indexer.process_job(job_id=job_id)
