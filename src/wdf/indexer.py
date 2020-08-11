import logging
import time
from datetime import datetime

import pytz
from dateutil.parser import parse as date_parse
from django.conf import settings
from scrapinghub import ScrapinghubClient

from wdf.models import (
    DictBrand, DictCatalog, DictMarketplace, DictParameter, Dump, Parameter, Position, Price, Rating, Reviews, Sales,
    Sku, Version)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Indexer(object):
    """ Маркетплейс мы знаем всегда и найти (или добавить его) нам нужно только один раз.
    Бренды на данный момент уникальны для каждого SKU (хотя можно пытаться угадать ссылку на бренд из ссылки анализа)
    Параметры уникальны для каждого SKU, даже если мы анализируем конкретный каталог.

    По категории есть три ситуации:

    1. Мы разбираем выгрузку по категории
    2. Мы разбираем общую выгрузку
    3. Мы разбираем какую-то непонятную выгрузку (например, по поисковой фразе)

    В случае (1) мы знаем категорию и можем ее не искать каждый раз (хотя кеш никто не отменял)
    В случае (2) мы должны для каждого SKU подобрать свою категорию (и закешировать ее по ссылке)

    План такой.

    Этап I (словари):
    1. Берем один батч (из n айтемов). Разбираем его по переменным
    2. Составляем список каталогов, брендов, продавцов и параметров из батча в словарях DictMarketplace,
       DictCatalog, DictParameter, DictBrand, DictSeller
    3. Убираем все, которые есть уже в in-memory кеше (в переменной-списке)
    4. Стартуем транзакцию (опционально)
    5. По тем, которых нет в кеше, делаем запрос в БД
    6. Добавляем в кеш все, что нашлось
    7. По всем, что не нашлись, создаем записи, укладываем их в кеш
    8. Останавливаем транзакцию (опционально)

    Этап II (добавление позиций):
    1. Ичищаем кеш SKU (или нет)
    2. Составляем список позиций из батча
    3. Стартуем транзакцию (опционально)
    4. Делаем запрос по ним в БД
    5. Добавляем в кеш все, что нашлось
    6. По всем, что не нашлись, создаем записи, укладываем их в кеш
    7. Останавливаем транзакцию (опционально)

    Этап III (подготовка к записи версии):
    1. Делаем новую запись в Dump
    2. Готовим датасет со всеми ID SKU и словарей для записи
    3. Проходимся по датасету, для каждой записи делаем Version и записываем данные в Price, Rating, Sales,
       Position, Seller, Reviews, Parameter

    Работа с памятью:
    а) Можно контролировать память и при достижении критического значения обнулять кеши.
    б) Можно использовать структуры данных (какие?), в которых редко запрашиваемые значения очищаются.

    Работа со скоростью:
    а) Фиксировать скорость обработки записей (шт/сек) и изменение этого значения

    Работа с блокировками и race condition:
    а) Можно делать работу в один поток (для начала, но вообще не стоит на это расчитывать в перспективе)
    б) Можно делать транзакции там, где есть риск параллельной записи  (таблицы словарей и SKU,
       в версиях такой проблемы быть не должно)
    в) После завершения работы скрипта можно проверять наличие дублей и устранять их
    г) Раз в сутки можно останавливать БД на запись, проверять наличие дублей и устранять их
    д) Можно сначала в один поток на всю систему обновлять словари, потом в много потоков писать данные о позициях,
       в этом случае никакого rc не должно быть
    """

    def __init__(self, stdout=None, style=None):
        self.spider_slug = 'wb'

        self.stdout = stdout
        self.style = style

        self.marketplace_model = self.get_marketplace_model(self.spider_slug)
        self.dump_model = None
        self.sh_client = ScrapinghubClient(settings.SH_APIKEY)
        self.generator = None

        self.catalog_cache = {}
        self.brand_cache = {}
        self.sku_cache = {}
        self.parameter_cache = {}

        self.catalogs = {}
        self.brands = {}
        self.skus = {}
        self.parameters = {}

    def process_job(self, job_id, chunk_size=500):
        if Dump.objects.filter(job=job_id).count() > 0:
            logger.warning(f'Dump for job {job_id} already exists, skipping')

            return

        self.generator = self.get_generator(job_id=job_id, chunk_size=chunk_size)
        self.dump_model = self.save_dump(self.spider_slug, job_id)

        chunk_no = 1
        for chunk in self.generator:
            start_time = time.time()

            self.clear_collections()

            for item in chunk:
                self.collect_all(item)

            self.update_all_caches(self.catalogs, self.brands, self.parameters, self.skus)

            # Записываем версии для каждого артикула
            for item in chunk:
                version = self.save_version(item)

                self.save_all(version, item)

            time_spent = time.time() - start_time

            logger.info(f'Chunk #{chunk_no} processed in {time_spent}s, {round(len(chunk) / time_spent * 60)} items/min')

            chunk_no += 1

        self.dump_model.state = 'finished'
        self.dump_model.save()

    def get_generator(self, job_id, chunk_size=500):
        return self.sh_client.get_job(job_id).items.list_iter(chunksize=chunk_size)

    def get_marketplace_model(self, spider_slug):
        try:
            marketplace_model = DictMarketplace.objects.get(slug=spider_slug)
        except DictMarketplace.DoesNotExist:
            marketplace_model = DictMarketplace(name=spider_slug, slug=spider_slug)

            marketplace_model.save()

        return marketplace_model

    def save_all(self, version, item):
        self.save_price(version, item)
        self.save_rating(version, item)
        self.save_sales(version, item)
        self.save_reviews(version, item)
        self.save_parameters(version, item)
        self.save_position(version, item)

    def save_dump(self, spider_slug, job_id):
        job_metadata = self.sh_client.get_job(job_id).metadata

        dump = Dump(
            crawler=spider_slug,
            job=job_id,
            crawl_started_at=pytz.utc.localize(datetime.fromtimestamp(job_metadata.get('running_time') / 1000)),
            crawl_ended_at=pytz.utc.localize(datetime.fromtimestamp(job_metadata.get('finished_time') / 1000)),
            state='processing',
            items_crawled=job_metadata.get('scrapystats')['item_scraped_count'],
        )

        dump.save()

        return dump

    def save_version(self, item):
        version = Version(
            dump=self.dump_model,
            sku_id=self.sku_cache[item['wb_id']],
            crawled_at=pytz.utc.localize(date_parse(item['parse_date'])),
        )

        version.save()

        return version

    def save_position(self, version, item):
        if 'wb_category_position' in item.keys():
            position = Position(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                catalog_id=self.catalog_cache[item['wb_category_url']],
                absolute=item['wb_category_position'],
            )

            position.save()

            return position

    def save_price(self, version, item):
        if 'wb_price' in item.keys():
            price = Price(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                price=float(item['wb_price']),
            )

            price.save()

            return price

    def save_rating(self, version, item):
        if 'wb_rating' in item.keys():
            rating = Rating(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                rating=item['wb_rating'],
            )

            rating.save()

            return rating

    def save_sales(self, version, item):
        if 'wb_purchases_count' in item.keys():
            sales = Sales(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                sales=item['wb_purchases_count'],
            )

            sales.save()

            return sales

    def save_reviews(self, version, item):
        if 'wb_reviews_count' in item.keys():
            reviews = Reviews(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                reviews=item['wb_reviews_count'],
            )

            reviews.save()

            return reviews

    def save_parameters(self, version, item):
        if 'features' in item.keys():
            parameters = []

            for feature_name, feature_value in item['features'][0].items():
                parameter = Parameter(
                    sku_id=self.sku_cache[item['wb_id']],
                    version=version,
                    parameter_id=self.parameter_cache[feature_name],
                    value=feature_value,
                )

                parameter.save()

                parameters.append(parameter)

            return parameters

    def clear_collections(self):
        self.catalogs = {}
        self.brands = {}
        self.parameters = {}
        self.skus = {}

    def collect_all(self, item):
        self.collect_wb_catalogs(item)
        self.collect_wb_brands(item)
        self.collect_wb_parameters(item)
        self.collect_wb_skus(item)

    def collect_wb_catalogs(self, item):
        if 'wb_category_url' in item.keys():
            self.catalogs[item['wb_category_url']] = {
                'marketplace': self.marketplace_model.id,
                'parent': '',
                'name': item['wb_category_name'] if 'wb_category_name' in item.keys() else None,
                'url': item['wb_category_url'] if 'wb_category_url' in item.keys() else None,
                'level': 1,
            }

    def collect_wb_brands(self, item):
        if 'wb_brand_url' in item.keys():
            self.brands[item['wb_brand_url']] = {
                'marketplace': self.marketplace_model.id,
                'name': item['wb_brand_name'] if 'wb_brand_name' in item.keys() else None,
                'url': item['wb_brand_url'] if 'wb_brand_url' in item.keys() else None,
            }

    def collect_wb_parameters(self, item):
        if 'features' in item.keys():
            for feature_name, _feature_value in item['features'][0].items():
                self.parameters[feature_name] = {
                    'marketplace': self.marketplace_model.id,
                    'name': feature_name,
                }

    def collect_wb_skus(self, item):
        self.skus[item['wb_id']] = {
            'parse_date': item['parse_date'],
            'marketplace': self.marketplace_model.id,
            'brand': item['wb_brand_url'] if 'wb_brand_url' in item.keys() else None,
            'article': item['wb_id'],
            'url': item['product_url'],
            'title': item['product_name'],
        }

    def update_all_caches(self, catalogs, brands, parameters, skus):
        self.update_catalogs_cache(catalogs)
        self.update_brands_cache(brands)
        self.update_parameters_cache(parameters)
        self.update_sku_cache(skus)

    def filter_items_not_found(self, retrieved, cache_attr_name, model, cache_key):
        # по этому фильтру будем искать в бд
        filter_key = cache_key + '__in'

        # смотрим каких записей нет в горячем кешк в памяти
        items_to_retrieve = set(retrieved.keys()).difference(set(getattr(self, cache_attr_name).keys()))

        # пытаемся найти их в бд
        items_retrieved = model.objects.filter(**{filter_key: items_to_retrieve})

        # сохраняем найденное в память
        setattr(self, cache_attr_name, {**getattr(self, cache_attr_name), **dict([(getattr(item, cache_key), item.id) for item in items_retrieved])})

        # разница между кешем и тем, что нужно было найти – ненайденные записи
        return set(retrieved.keys()).difference(set(getattr(self, cache_attr_name).keys()))

    def update_catalogs_cache(self, retrieved):
        for catalog_url in self.filter_items_not_found(self.catalogs, 'catalog_cache', DictCatalog, 'url'):
            new_model = DictCatalog(
                marketplace_id=retrieved[catalog_url]['marketplace'],
                parent_id=retrieved[catalog_url]['parent'],
                name=retrieved[catalog_url]['name'],
                url=retrieved[catalog_url]['url'],
                level=retrieved[catalog_url]['level'],
            )

            new_model.save()

            self.catalog_cache[catalog_url] = new_model.id

    def update_brands_cache(self, retrieved):
        for brand_url in self.filter_items_not_found(self.brands, 'brand_cache', DictBrand, 'url'):
            new_model = DictBrand(
                marketplace_id=retrieved[brand_url]['marketplace'],
                name=retrieved[brand_url]['name'],
                url=retrieved[brand_url]['url'],
            )

            new_model.save()

            self.brand_cache[brand_url] = new_model.id

    def update_parameters_cache(self, retrieved):
        for parameter_name in self.filter_items_not_found(self.parameters, 'parameter_cache', DictParameter, 'name'):
            new_model = DictParameter(
                marketplace_id=retrieved[parameter_name]['marketplace'],
                name=parameter_name,
            )

            new_model.save()

            self.parameter_cache[parameter_name] = new_model.id

    def update_sku_cache(self, retrieved):
        for sku_article in self.filter_items_not_found(self.skus, 'sku_cache', Sku, 'article'):
            new_model = Sku(
                marketplace_id=retrieved[sku_article]['marketplace'],
                brand_id=self.brand_cache[retrieved[sku_article]['brand']],
                article=retrieved[sku_article]['article'],
                url=retrieved[sku_article]['url'],
                title=retrieved[sku_article]['title'],
            )

            new_model.save()

            self.sku_cache[sku_article] = new_model.id
