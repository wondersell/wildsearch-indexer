from celery import shared_task
from requests.exceptions import RequestException

from wdf.indexer import Indexer


@shared_task(
    autoretry_for=[RequestException],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 5,
    },
)
def import_version(job_id):
    indexer = Indexer()
    indexer.process_job_end_to_end(job_id=job_id)


@shared_task(
    autoretry_for=[RequestException],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 5,
    },
)
def prepare_dump(job_id):
    indexer = Indexer()

    dump = indexer.prepare_dump(job_id=job_id)

    split_dump(dump_id=dump.id).delay()


@shared_task(
    autoretry_for=[RequestException],
    retry_kwargs={
        'max_retries': 10,
        'countdown': 5,
    },
)
def split_dump(job_id):
    indexer = Indexer()

    dump = indexer.get_or_save_dump('wb', job_id)

    workers_per_batch = 5

    batch_size = round(dump.items_crawled / workers_per_batch)

    for mark in range(0, dump.items_crawled, batch_size):
        import_dump_chunk(job_id, mark, batch_size).delay()


@shared_task()
def import_dump_chunk(job_id, start, count):
    indexer = Indexer()

    indexer.import_batch(job_id, start, count)
