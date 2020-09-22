import json
import os
import pytest
import requests_mock
from mixer.backend.django import mixer

from wdf.indexer import Indexer
from wdf.models import DictCatalog, DictParameter, Dump, Sku, Version


@pytest.fixture()
def current_path():
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture()
def indexer():
    return Indexer()


@pytest.fixture()
def sample_category_data_raw(current_path):
    def _sample_category_data_raw(spider='wb'):
        return open(current_path + f'/mocks/scrapinghub_items_{spider}_raw.msgpack', 'rb').read()

    return _sample_category_data_raw


@pytest.fixture()
def items_sample(current_path):
    with open(current_path + '/mocks/items_list.json') as f:
        return json.loads(f.read())


@pytest.fixture()
def item_sample(items_sample):
    return items_sample[0]


@pytest.fixture()
def indexer_filled(indexer, items_sample):
    for item in items_sample:
        indexer.collect_all(item)

    return indexer


@pytest.fixture()
def indexer_filled_with_caches(indexer_filled):
    indexer_filled.update_all_caches(
        indexer_filled.catalogs_retrieved,
        indexer_filled.brands_retrieved,
        indexer_filled.parameters_retrieved,
        indexer_filled.skus_retrieved,
    )

    return indexer_filled


@pytest.fixture()
def version_sample():
    return mixer.blend(Version)


@pytest.fixture()
def dump_sample():
    def _dump_sample(state=Dump.CREATED, job_id='12345/123/12345', crawler='wb'):
        dump = mixer.blend(Dump)

        dump.set_state(state)
        dump.job = job_id
        dump.crawler = crawler

        dump.save()

        return dump

    return _dump_sample


@pytest.fixture()
def sku_sample():
    return mixer.blend(Sku)


@pytest.fixture()
def dict_catalog_sample():
    return mixer.blend(DictCatalog)


@pytest.fixture()
def dict_parameter_sample():
    return mixer.blend(DictParameter)


@pytest.fixture()
def _fill_db(indexer_filled_with_caches, items_sample, dump_sample):
    dump_sample = dump_sample()

    indexer_filled_with_caches.process_batch([items_sample], dump_sample, save_versions=True)


@pytest.fixture(autouse=True)
def requests_mocker(current_path, sample_category_data_raw):
    """Mock all requests.
    This is an autouse fixture so that tests can't accidentally
    perform real requests without being noticed.
    """
    with requests_mock.Mocker() as m:
        m.get('https://storage.scrapinghub.com/jobs/12345/123/12345/running_time', text='1597854066275')
        m.get('https://storage.scrapinghub.com/jobs/12345/123/12345/finished_time', text='1597854164856')
        m.get('https://storage.scrapinghub.com/jobs/12345/123/12345/scrapystats', text=open(current_path + '/mocks/scrapystats.json', 'r').read())
        m.get('https://storage.scrapinghub.com/items/12345/123/12345?start=12345%2F123%2F12345%2F0&count=100&meta=_key', content=sample_category_data_raw(spider='wb'), headers={'Content-Type': 'application/x-msgpack; charset=UTF-8'})
        yield m
