import pytest
import pytz
from dateutil.parser import parse as date_parse
from mixer.backend.django import mixer

from wdf.indexer import guess_wb_article
from wdf.models import DictCatalog, Parameter, Position, Price, Rating, Reviews, Sales, Sku, Version


@pytest.mark.django_db
def test_indexer_init(indexer):
    from scrapinghub import ScrapinghubClient
    assert isinstance(indexer.sh_client, ScrapinghubClient)


@pytest.mark.django_db
def test_collect_wb_catalogs_correct(indexer, item_sample):
    indexer.collect_wb_catalogs(item_sample)

    collected = indexer.catalogs['https://www.wildberries.ru/promotions/dlya-pitomtsev/kovriki-dlya-lotkov']

    assert len(indexer.catalogs) == 1
    assert list(collected) == ['marketplace', 'parent', 'name', 'url', 'level']
    assert collected['parent'] == ''
    assert collected['name'] == 'Коврики для лотков'
    assert collected['url'] == 'https://www.wildberries.ru/promotions/dlya-pitomtsev/kovriki-dlya-lotkov'
    assert collected['level'] == 1


@pytest.mark.django_db
def test_collect_wb_catalogs_empty_category(indexer, item_sample):
    item_sample.pop('wb_category_url', None)

    indexer.collect_wb_catalogs(item_sample)

    assert len(indexer.catalogs) == 0


@pytest.mark.django_db
def test_collect_wb_brands_correct(indexer, item_sample):
    indexer.collect_wb_brands(item_sample)

    collected = indexer.brands['https://www.wildberries.ru/brands/vita-famoso']

    assert len(indexer.brands) == 1
    assert list(collected) == ['marketplace', 'name', 'url']
    assert collected['name'] == 'Vita Famoso'
    assert collected['url'] == 'https://www.wildberries.ru/brands/vita-famoso'


@pytest.mark.django_db
def test_collect_wb_brands_empty(indexer, item_sample):
    item_sample.pop('wb_brand_url', None)

    indexer.collect_wb_brands(item_sample)

    assert len(indexer.brands) == 0


@pytest.mark.django_db
def test_collect_wb_skus_correct(indexer, item_sample):
    indexer.collect_wb_skus(item_sample)

    collected = indexer.skus['11743005']

    assert len(indexer.skus) == 1
    assert list(collected) == ['parse_date', 'marketplace', 'brand', 'article', 'url', 'title']
    assert collected['parse_date'] == '2020-08-10 18:12:07.478756'
    assert collected['brand'] == 'https://www.wildberries.ru/brands/vita-famoso'
    assert collected['article'] == '11743005'
    assert collected['url'] == 'https://www.wildberries.ru/catalog/11743005/detail.aspx'
    assert collected['title'] == 'Коврик для туалета кошки, кошачий коврик под лоток для кошки'


@pytest.mark.django_db
def test_collect_parameters_correct(indexer, item_sample):
    indexer.collect_wb_parameters(item_sample)

    assert len(indexer.parameters) == 10
    assert list(indexer.parameters.keys()) == ['Вид животного', 'Материал изделия', 'Вес с упаковкой (кг)', 'Ширина предмета', 'Длина предмета', 'Ширина упаковки', 'Длина упаковки', 'Комплектация', 'Страна бренда', 'Страна производитель']


@pytest.mark.django_db
def test_collect_all(indexer, item_sample):
    indexer.collect_all(item_sample)

    assert len(indexer.skus) == 1
    assert len(indexer.brands) == 1
    assert len(indexer.catalogs) == 1
    assert len(indexer.parameters) == 10


@pytest.mark.django_db
def test_clear_collections(indexer, item_sample):
    indexer.collect_all(item_sample)
    indexer.clear_collections()

    assert len(indexer.skus) == 0
    assert len(indexer.brands) == 0
    assert len(indexer.catalogs) == 0
    assert len(indexer.parameters) == 0


@pytest.mark.django_db
def test_filter_items_not_found_empty_cache(indexer, items_sample):
    for item in items_sample:
        indexer.collect_all(item)

    not_found = indexer.filter_items_not_found(indexer.skus, 'sku_cache', Sku, 'article')

    assert len(not_found) == 26
    assert '11743005' in not_found


@pytest.mark.django_db
def test_filter_items_not_found_filled_cache(indexer_filled, items_sample):
    mixer.cycle(6).blend(Sku, article=(_ for _ in ('11743005', '12381016', '13168135', '13194636', '12325577', '11784593')))

    not_found = indexer_filled.filter_items_not_found(indexer_filled.skus, 'sku_cache', Sku, 'article')

    assert len(not_found) == 20  # из 26


@pytest.mark.django_db
def test_update_catalogs_cache_empty_cache(indexer, item_sample):
    indexer.collect_all(item_sample)

    indexer.update_catalogs_cache(indexer.catalogs)

    assert len(indexer.catalog_cache) == 1


@pytest.mark.django_db
def test_update_catalogs_cache_filled_cache_with_object(indexer, item_sample):
    indexer.collect_all(item_sample)

    mixer.blend(DictCatalog, url='https://www.wildberries.ru/catalog/yuvelirnye-ukrasheniya/koltsa/pechatki')

    indexer.update_catalogs_cache(indexer.catalogs)

    assert len(indexer.catalog_cache) == 1


@pytest.mark.django_db
def test_update_catalogs_cache_filled_cache_without_object(indexer, item_sample):
    indexer.collect_all(item_sample)
    mixer.blend(DictCatalog)

    indexer.update_catalogs_cache(indexer.catalogs)

    assert len(indexer.catalog_cache) == 1


@pytest.mark.django_db
def test_update_brands_cache_empty_cache(indexer_filled):
    indexer_filled.update_brands_cache(indexer_filled.brands)

    assert len(indexer_filled.brand_cache) == 9


@pytest.mark.django_db
def test_update_parameters_cache_empty_cache(indexer_filled):
    indexer_filled.update_parameters_cache(indexer_filled.parameters)

    assert len(indexer_filled.parameter_cache) == 16


@pytest.mark.django_db
def test_update_sku_cache_empty_cache(indexer_filled):
    indexer_filled.update_brands_cache(indexer_filled.brands)
    indexer_filled.update_sku_cache(indexer_filled.skus)

    assert len(indexer_filled.sku_cache) == 26


@pytest.mark.django_db
def test_update_sku_cache_without_brands(indexer_filled):
    indexer_filled.update_sku_cache(indexer_filled.skus)

    assert len(indexer_filled.sku_cache) == 26


@pytest.mark.django_db
def test_update_all_caches(indexer_filled):
    indexer_filled.update_all_caches(indexer_filled.catalogs, indexer_filled.brands, indexer_filled.parameters, indexer_filled.skus)

    assert len(indexer_filled.catalog_cache) == 1
    assert len(indexer_filled.brand_cache) == 9
    assert len(indexer_filled.parameter_cache) == 16
    assert len(indexer_filled.sku_cache) == 26


@pytest.mark.django_db
def test_save_version(indexer_filled_with_caches, dump_sample, item_sample):
    indexer_filled_with_caches.save_version(dump_sample, item_sample)

    assert len(Version.objects.all()) == 1

    obj = Version.objects.first()

    assert obj.sku.article == '11743005'
    assert obj.crawled_at == pytz.utc.localize(date_parse('2020-08-10 18:12:07.478756'))


@pytest.mark.django_db
def test_save_position(indexer_filled_with_caches, item_sample, version_sample):
    indexer_filled_with_caches.save_position(version_sample, item_sample)

    assert len(Position.objects.all()) == 1

    obj = Position.objects.first()

    assert obj.sku.article == '11743005'
    assert obj.absolute == 3


@pytest.mark.django_db
def test_save_position_empty(indexer_filled_with_caches, item_sample, version_sample):
    item_sample.pop('wb_category_position', None)

    indexer_filled_with_caches.save_position(version_sample, item_sample)

    assert len(Position.objects.all()) == 0


@pytest.mark.django_db
def test_save_price(indexer_filled_with_caches, item_sample, version_sample):
    indexer_filled_with_caches.save_price(version_sample, item_sample)

    assert len(Price.objects.all()) == 1

    obj = Price.objects.first()

    assert obj.sku.article == '11743005'
    assert obj.price == 800


@pytest.mark.django_db
def test_save_price_empty(indexer_filled_with_caches, item_sample, version_sample):
    item_sample.pop('wb_price', None)

    indexer_filled_with_caches.save_price(version_sample, item_sample)

    assert len(Price.objects.all()) == 0


@pytest.mark.django_db
def test_save_rating(indexer_filled_with_caches, item_sample, version_sample):
    indexer_filled_with_caches.save_rating(version_sample, item_sample)

    assert len(Rating.objects.all()) == 1

    obj = Rating.objects.first()

    assert obj.sku.article == '11743005'
    assert obj.rating == 4


@pytest.mark.django_db
def test_save_rating_empty(indexer_filled_with_caches, item_sample, version_sample):
    item_sample.pop('wb_rating', None)

    indexer_filled_with_caches.save_rating(version_sample, item_sample)

    assert len(Rating.objects.all()) == 0


@pytest.mark.django_db
def test_save_sales(indexer_filled_with_caches, item_sample, version_sample):
    indexer_filled_with_caches.save_sales(version_sample, item_sample)

    assert len(Sales.objects.all()) == 1

    obj = Sales.objects.first()

    assert obj.sku.article == '11743005'
    assert obj.sales == 200


@pytest.mark.django_db
def test_save_sales_empty(indexer_filled_with_caches, item_sample, version_sample):
    item_sample.pop('wb_purchases_count', None)

    indexer_filled_with_caches.save_sales(version_sample, item_sample)

    assert len(Sales.objects.all()) == 0


@pytest.mark.django_db
def test_save_reviews(indexer_filled_with_caches, item_sample, version_sample):
    indexer_filled_with_caches.save_reviews(version_sample, item_sample)

    assert len(Reviews.objects.all()) == 1

    obj = Reviews.objects.first()

    assert obj.sku.article == '11743005'
    assert obj.reviews == 19


@pytest.mark.django_db
def test_save_reviews_empty(indexer_filled_with_caches, item_sample, version_sample):
    item_sample.pop('wb_reviews_count', None)

    indexer_filled_with_caches.save_reviews(version_sample, item_sample)

    assert len(Reviews.objects.all()) == 0


@pytest.mark.django_db
def test_save_parameters(indexer_filled_with_caches, item_sample, version_sample):
    indexer_filled_with_caches.save_parameters(version_sample, item_sample)

    assert len(Parameter.objects.all()) == 10

    obj = Parameter.objects.first()

    assert obj.sku.article == '11743005'
    assert obj.parameter.name == 'Вид животного'
    assert obj.value == 'для кошек; для собак'


@pytest.mark.django_db
def test_save_parameters_empty(indexer_filled_with_caches, item_sample, version_sample):
    item_sample.pop('features', None)

    indexer_filled_with_caches.save_parameters(version_sample, item_sample)

    assert len(Parameter.objects.all()) == 0


@pytest.mark.django_db
def test_save_all(indexer_filled_with_caches, item_sample, version_sample):
    indexer_filled_with_caches.save_all(version_sample, item_sample)

    assert len(Version.objects.all()) == 1
    assert len(Position.objects.all()) == 1
    assert len(Price.objects.all()) == 1
    assert len(Rating.objects.all()) == 1
    assert len(Sales.objects.all()) == 1
    assert len(Reviews.objects.all()) == 1
    assert len(Parameter.objects.all()) == 10


@pytest.mark.django_db
@pytest.mark.parametrize(('sample_item', 'expected_article'), [
    ({'wb_id': '12345', 'product_url': 'https://www.wildberries.ru/catalog/7402496/detail.aspx'}, '12345'),
    ({'wb_id': '2020-08-13 03:00:45.275365', 'product_url': 'https://www.wildberries.ru/catalog/7402496/detail.aspx'}, '7402496'),
    ({'wb_id': '52423', 'product_url': 'https://www.wildberries.ru/catalog/7402496/detail.aspx'}, '52423'),
])
def test_guess_wb_article(sample_item, expected_article):
    article = guess_wb_article(sample_item)

    assert article == expected_article
