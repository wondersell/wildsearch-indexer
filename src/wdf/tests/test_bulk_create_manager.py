import pytest

from wdf.bulk_create_manager import BulkCreateManager


class DummyMeta:
    label = 'dummy'


class DummyModel:
    _meta = DummyMeta


@pytest.fixture
def n_models():
    def _n_models(count):
        return [DummyModel() for _ in range(count)]

    return _n_models


def test_split_in_chunks(n_models):
    manager = BulkCreateManager(max_chunk_size=3)
    models = n_models(count=10)

    for model in models:
        manager.add(model)

    chunks = manager._split_in_slices(manager._pg_copy_create_queues['dummy'])

    assert len(chunks) == 4
    assert len(chunks[0]) == 3
    assert len(chunks[-1]) == 1
