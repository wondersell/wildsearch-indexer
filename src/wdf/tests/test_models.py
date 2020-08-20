import pytest
from django.db.utils import IntegrityError

from wdf.models import (
    DictBrand, DictCatalog, DictMarketplace, DictParameter, Dump, Parameter, Position, Price, Rating, Reviews, Sales,
    Sku, Version)


@pytest.mark.usefixtures('_fill_db')
@pytest.mark.django_db
def test_delete_dump():
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


@pytest.mark.django_db
@pytest.mark.parametrize(('state_code', 'state'), [
    (0, 'created'),
    (5, 'preparing'),
    (10, 'prepared'),
    (15, 'scheduling'),
    (20, 'scheduled'),
    (25, 'processing'),
    (30, 'processed'),
])
def test_set_state(state_code, state, dump_sample):
    dump_sample.set_state(state_code)

    assert dump_sample.state == state
    assert dump_sample.state_code == state_code


@pytest.mark.django_db
def test_unique_constraint_price(sku_sample, version_sample):
    try:
        price_1 = Price(sku=sku_sample, version=version_sample, price=999.9)
        price_1.save()

        price_2 = Price(sku=sku_sample, version=version_sample, price=999.9)
        price_2.save()

        pytest.fail('Price constraint failed')
    except IntegrityError:
        assert True


@pytest.mark.django_db
def test_unique_constraint_rating(sku_sample, version_sample):
    try:
        rating_1 = Rating(sku=sku_sample, version=version_sample, rating=4.0)
        rating_1.save()

        rating_2 = Rating(sku=sku_sample, version=version_sample, rating=4.0)
        rating_2.save()

        pytest.fail('Rating constraint failed')
    except IntegrityError:
        assert True


@pytest.mark.django_db
def test_unique_constraint_sales(sku_sample, version_sample):
    try:
        sales_1 = Sales(sku=sku_sample, version=version_sample, sales=999)
        sales_1.save()

        sales_2 = Sales(sku=sku_sample, version=version_sample, sales=999)
        sales_2.save()

        pytest.fail('Sales constraint failed')
    except IntegrityError:
        assert True


@pytest.mark.django_db
def test_unique_constraint_position(sku_sample, version_sample, dict_catalog_sample):
    try:
        position_1 = Position(sku=sku_sample, version=version_sample, catalog=dict_catalog_sample, absolute=999)
        position_1.save()

        position_2 = Position(sku=sku_sample, version=version_sample, catalog=dict_catalog_sample, absolute=999)
        position_2.save()

        pytest.fail('Position constraint failed')
    except IntegrityError:
        assert True


@pytest.mark.django_db
def test_unique_constraint_reviews(sku_sample, version_sample):
    try:
        reviews_1 = Reviews(sku=sku_sample, version=version_sample, reviews=99)
        reviews_1.save()

        reviews_2 = Reviews(sku=sku_sample, version=version_sample, reviews=99)
        reviews_2.save()

        pytest.fail('Reviews constraint failed')
    except IntegrityError:
        assert True


@pytest.mark.django_db
def test_unique_constraint_parameter(sku_sample, version_sample, dict_parameter_sample):
    try:
        parameter_1 = Parameter(sku=sku_sample, version=version_sample, parameter=dict_parameter_sample, value='foo')
        parameter_1.save()

        parameter_2 = Parameter(sku=sku_sample, version=version_sample, parameter=dict_parameter_sample, value='foo')
        parameter_2.save()

        pytest.fail('Parameter constraint failed')
    except IntegrityError:
        assert True
