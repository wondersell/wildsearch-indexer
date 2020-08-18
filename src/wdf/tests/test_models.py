import pytest

from wdf.models import (
    DictBrand, DictCatalog, DictMarketplace, DictParameter, Dump, Parameter, Position, Price, Rating, Reviews, Sales,
    Sku, Version)


@pytest.mark.django_db
def test_delete_dump(_fill_db):
    # проверяем, что всё на месте после загрузки БД
    assert len(Dump.objects.all()) == 1
    assert len(Version.objects.all()) == 26
    assert len(Sku.objects.all()) == 26
    assert len(Price.objects.all()) == 26
    assert len(Rating.objects.all()) == 26
    assert len(Sales.objects.all()) == 26
    assert len(Position.objects.all()) == 24
    assert len(Reviews.objects.all()) == 26
    assert len(Parameter.objects.all()) == 215
    assert len(DictMarketplace.objects.all()) == 1
    assert len(DictBrand.objects.all()) == 9
    assert len(DictCatalog.objects.all()) == 1
    assert len(DictParameter.objects.all()) == 16

    # Удаляем дамп
    dump = Dump.objects.first()
    dump.delete()

    # Проверяем, что с дампом удалилось всё ненужное и не удалилось ничего нужного
    assert len(Dump.objects.all()) == 0
    assert len(Version.objects.all()) == 0
    assert len(Sku.objects.all()) == 26
    assert len(Price.objects.all()) == 0
    assert len(Rating.objects.all()) == 0
    assert len(Sales.objects.all()) == 0
    assert len(Position.objects.all()) == 0
    assert len(Reviews.objects.all()) == 0
    assert len(Parameter.objects.all()) == 0
    assert len(DictMarketplace.objects.all()) == 1
    assert len(DictBrand.objects.all()) == 9
    assert len(DictCatalog.objects.all()) == 1
    assert len(DictParameter.objects.all()) == 16
