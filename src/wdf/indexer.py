import environ
import logging
import pytz
import re
import resource
import sys
import time
from datetime import datetime
from dateutil.parser import parse as date_parse
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from scrapinghub import ScrapinghubClient

from wdf.bulk_create_manager import BulkCreateManager
from wdf.exceptions import DumpCorruptedError
from wdf.models import (
    DictBrand, DictCatalog, DictMarketplace, DictParameter, Dump, Parameter, Position, Price, Rating, Reviews, Sales,
    Sku, Version)

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()

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

    def __init__(self, job_id):
        self.spider_slug = 'wb'
        self.get_chunk_size = env('INDEXER_GET_CHUNK_SIZE', cast=int)
        self.save_chunk_size = env('INDEXER_SAVE_CHUNK_SIZE', cast=int)

        self.marketplace, new_marketplace = DictMarketplace.objects.get_or_create(name=self.spider_slug, slug=self.spider_slug)
        self.dump, new_dump = Dump.objects.get_or_create(job=job_id, crawler=self.spider_slug)

        self.sh_client = ScrapinghubClient(settings.SH_APIKEY)
        self.bulk_manager = BulkCreateManager(max_chunk_size=self.save_chunk_size)

        self.catalogs_cache = {}
        self.brands_cache = {}
        self.skus_cache = {}
        self.parameters_cache = {}

        self.catalogs_retrieved = {}
        self.brands_retrieved = {}
        self.skus_retrieved = {}
        self.parameters_retrieved = {}

        self.log_prefix = ''

        if new_dump or self.dump.items_crawled is None or self.dump.crawl_ended_at is None or self.dump.crawl_ended_at is None:
            self.load_dump_stats(self.dump)

    def set_chunk_size_save(self, size):
        self.save_chunk_size = size

        return self

    def set_chunk_size_get(self, size):
        self.get_chunk_size = size

        return self

    def prepare_dump(self, start=0, count=sys.maxsize):
        generator = self.get_generator(start=start, count=count, chunk_size=self.get_chunk_size)

        if self.dump.state_code > 0:
            logger.info(f'Dump already prepared (state code {self.dump.state_code} – {self.dump.state}), skipping prepare step')

            return self

        self.dump.set_state(Dump.PREPARING)
        self.dump.save()

        self.process_batch(generator=generator, save_versions=False)

        self.dump.set_state(Dump.PREPARED)
        self.dump.save()

        return self

    @transaction.atomic
    def import_dump(self, start=0, count=sys.maxsize):
        generator = self.get_generator(start=start, count=count, chunk_size=self.get_chunk_size)

        if self.dump.state_code > 25:
            logger.info(f'Dump already imported (state code {self.dump.state_code} – {self.dump.state}), skipping import step')

            return self

        self.dump.set_state(Dump.PROCESSING)
        self.dump.save()

        self.process_batch(generator=generator, save_versions=True)

        return self

    def wrap_dump(self):
        versions_num = self.dump.get_versions_num()

        if versions_num > self.dump.items_crawled:
            raise DumpCorruptedError('Dump has more versions than job')

        if versions_num < self.dump.items_crawled:
            raise DumpCorruptedError('Dump has less versions than job')

        self.dump.set_state(Dump.PROCESSED)
        self.dump.save()

    def process_batch(self, generator, save_versions=False):
        overall_start_time = time.time()

        chunk_no = 1
        items_count = 0

        for chunk in generator:
            self.log_prefix = f'Job {self.dump.job}, chunk #{chunk_no}: '

            try:
                log_action = 'Prepared'

                start_time = time.time()
                mem_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024  # в мегабайтах

                self.clear_retrieved()
                self.clear_caches()

                for item in chunk:
                    self.collect_all(item)

                    items_count += 1

                self.update_all_caches(self.catalogs_retrieved, self.brands_retrieved, self.parameters_retrieved, self.skus_retrieved)

                if save_versions:
                    log_action = 'Saved'

                    self.save_all(chunk)

                    self.bulk_manager.done(log_prefix=self.log_prefix)

                time_spent = time.time() - start_time

                logger.info(f'{self.log_prefix}{log_action} in {time_spent}s, {round(len(chunk) / time_spent * 60)} items/min, used {round(mem_usage, 2)}MB')

                chunk_no += 1
            except KeyboardInterrupt:
                # В основном для отладки через систему команд Django
                overall_time_spent = time.time() - overall_start_time

                logger.info(f'{self.dump} ({self.dump.job}) processed in {overall_time_spent}s, {round(items_count / overall_time_spent * 60)} items/min')

                raise SystemExit(0)

        overall_time_spent = time.time() - overall_start_time

        logger.info(f'{self.log_prefix}Processed in {overall_time_spent}s, {round(items_count / overall_time_spent * 60)} items/min')

        return self

    def get_generator(self, chunk_size=500, start=0, count=sys.maxsize):
        return self.sh_client.get_job(self.dump.job).items.list_iter(chunksize=chunk_size, start=start, count=count)

    def load_dump_stats(self, dump_model):
        job_metadata = self.sh_client.get_job(dump_model.job).metadata

        dump_model.crawl_started_at = pytz.utc.localize(datetime.fromtimestamp(job_metadata.get('running_time') / 1000))
        dump_model.crawl_ended_at = pytz.utc.localize(datetime.fromtimestamp(job_metadata.get('finished_time') / 1000))
        dump_model.items_crawled = job_metadata.get('scrapystats')['item_scraped_count']

        dump_model.save()

    def save_all(self, chunk):
        for item in chunk:
            version = self.save_version(item=item)

            self.save_price(version, item)
            self.save_rating(version, item)
            self.save_sales(version, item)
            self.save_reviews(version, item)
            self.save_parameters(version, item)
            self.save_position(version, item)

        self.bulk_manager.done(log_prefix=self.log_prefix)

    def save_version(self, item):
        version = Version(
            dump=self.dump,
            sku_id=self.skus_cache[item['wb_id']],
            crawled_at=pytz.utc.localize(date_parse(item['parse_date'])),
            created_at=timezone.now(),
        )

        self.bulk_manager.add(version)

        return version

    def save_position(self, version, item):
        if 'wb_category_position' in item.keys():
            self.bulk_manager.add(Position(
                sku_id=self.skus_cache[item['wb_id']],
                version=version,
                catalog_id=self.catalogs_cache[item['wb_category_url']],
                absolute=item['wb_category_position'],
                created_at=timezone.now(),
            ))

    def save_price(self, version, item):
        if 'wb_price' in item.keys():
            self.bulk_manager.add(Price(
                sku_id=self.skus_cache[item['wb_id']],
                version=version,
                price=float(item['wb_price']),
                created_at=timezone.now(),
            ))

    def save_rating(self, version, item):
        if 'wb_rating' in item.keys():
            self.bulk_manager.add(Rating(
                sku_id=self.skus_cache[item['wb_id']],
                version=version,
                rating=item['wb_rating'],
                created_at=timezone.now(),
            ))

    def save_sales(self, version, item):
        if 'wb_purchases_count' in item.keys():
            self.bulk_manager.add(Sales(
                sku_id=self.skus_cache[item['wb_id']],
                version=version,
                sales=item['wb_purchases_count'],
                created_at=timezone.now(),
            ))

    def save_reviews(self, version, item):
        if 'wb_reviews_count' in item.keys():
            self.bulk_manager.add(Reviews(
                sku_id=self.skus_cache[item['wb_id']],
                version=version,
                reviews=0 if item['wb_reviews_count'] == '' else item['wb_reviews_count'],
                created_at=timezone.now(),
            ))

    def save_parameters(self, version, item):
        if 'features' in item.keys():
            for feature_name, feature_value in item['features'][0].items():
                self.bulk_manager.add(Parameter(
                    sku_id=self.skus_cache[item['wb_id']],
                    version=version,
                    parameter_id=self.parameters_cache[feature_name],
                    value=feature_value,
                    created_at=timezone.now(),
                ))

    def clear_retrieved(self):
        self.catalogs_retrieved = {}
        self.brands_retrieved = {}
        self.parameters_retrieved = {}
        self.skus_retrieved = {}

    def clear_caches(self):
        self.catalogs_cache = {}
        self.brands_cache = {}
        self.parameters_cache = {}
        self.skus_cache = {}

    def collect_all(self, item):
        self.collect_wb_catalogs(item)
        self.collect_wb_brands(item)
        self.collect_wb_parameters(item)
        self.collect_wb_skus(item)

    def collect_wb_catalogs(self, item):
        if 'wb_category_url' in item.keys():
            self.catalogs_retrieved[item['wb_category_url']] = {
                'marketplace': self.marketplace.id,
                'parent': '',
                'name': item['wb_category_name'] if 'wb_category_name' in item.keys() else item['wb_category_url'],
                'url': item['wb_category_url'] if 'wb_category_url' in item.keys() else None,
                'level': 1,
            }

    def collect_wb_brands(self, item):
        if 'wb_brand_url' in item.keys():
            self.brands_retrieved[item['wb_brand_url']] = {
                'marketplace': self.marketplace.id,
                'name': item['wb_brand_name'] if 'wb_brand_name' in item.keys() else None,
                'url': item['wb_brand_url'] if 'wb_brand_url' in item.keys() else None,
            }

    def collect_wb_parameters(self, item):
        if 'features' in item.keys():
            for feature_name, _feature_value in item['features'][0].items():
                self.parameters_retrieved[feature_name] = {
                    'marketplace': self.marketplace.id,
                    'name': feature_name,
                }

    def collect_wb_skus(self, item):
        sku_title = item['product_name']
        max_length = Sku._meta.get_field('title').max_length

        if len(sku_title) > max_length:
            sku_title = sku_title[0:max_length - 1]

        self.skus_retrieved[item['wb_id']] = {
            'parse_date': item['parse_date'],
            'marketplace': self.marketplace.id,
            'brand': item['wb_brand_url'] if 'wb_brand_url' in item.keys() else None,
            'article': guess_wb_article(item),
            'url': item['product_url'],
            'title': sku_title,
        }

    def update_all_caches(self, catalogs, brands, parameters, skus):
        self.update_catalogs_cache(catalogs)
        self.update_brands_cache(brands)
        self.update_parameters_cache(parameters)
        self.update_sku_cache(skus)

    # Обновление горячего кеша объектов в памяти данными, которые есть в БД
    def update_caches_from_db(self, object_name, model, cache_key):
        model_key = model._meta.label

        start_time = time.time()

        retrieved_attr_name = object_name + '_retrieved'
        cached_attr_name = object_name + '_cache'

        retrieved = getattr(self, retrieved_attr_name)
        cached = getattr(self, cached_attr_name)

        # по этому фильтру будем искать в бд
        filter_key = cache_key + '__in'

        # смотрим каких записей нет в горячем кеше в памяти
        items_to_retrieve = set(retrieved.keys()).difference(set(cached.keys()))

        # пытаемся найти их в бд
        items_retrieved = model.objects.filter(**{filter_key: items_to_retrieve})

        # сохраняем найденное в память
        setattr(self, cached_attr_name, {**getattr(self, cached_attr_name),
                                         **dict([(getattr(item, cache_key), item.id) for item in items_retrieved])})

        items_count = len(items_retrieved)

        time_spent = time.time() - start_time

        logger.info(
            f'{self.log_prefix}{model_key} objects retrieved from DB ({items_count} items) in {time_spent}s, {round(items_count / time_spent * 60)} items/min')

    # Поиск несуществующих в кеше объектов
    def filter_items_not_found(self, object_name, model, cache_key):
        retrieved = getattr(self, object_name + '_retrieved')
        cached = getattr(self, object_name + '_cache')

        # разница между кешем и тем, что нужно было найти – ненайденные записи
        return set(retrieved.keys()).difference(set(cached.keys()))

    def update_catalogs_cache(self, retrieved):
        self.update_caches_from_db('catalogs', DictCatalog, 'url')

        for catalog_url in self.filter_items_not_found('catalogs', DictCatalog, 'url'):
            self.bulk_manager.add(DictCatalog(
                marketplace_id=retrieved[catalog_url]['marketplace'],
                parent_id=retrieved[catalog_url]['parent'] or None,
                name=retrieved[catalog_url]['name'],
                url=retrieved[catalog_url]['url'],
                level=retrieved[catalog_url]['level'],
                created_at=timezone.now(),
            ))

        self.bulk_manager.done(log_prefix=self.log_prefix)

        self.update_caches_from_db('catalogs', DictCatalog, 'url')

    def update_brands_cache(self, retrieved):
        self.update_caches_from_db('brands', DictBrand, 'url')

        for brand_url in self.filter_items_not_found('brands', DictBrand, 'url'):
            self.bulk_manager.add(DictBrand(
                marketplace_id=retrieved[brand_url]['marketplace'],
                name=retrieved[brand_url]['name'],
                url=retrieved[brand_url]['url'],
                created_at=timezone.now(),
            ))

        self.bulk_manager.done(log_prefix=self.log_prefix)

        self.update_caches_from_db('brands', DictBrand, 'url')

    def update_parameters_cache(self, retrieved):
        self.update_caches_from_db('parameters', DictParameter, 'name')

        for parameter_name in self.filter_items_not_found('parameters', DictParameter, 'name'):
            self.bulk_manager.add(DictParameter(
                marketplace_id=retrieved[parameter_name]['marketplace'],
                name=parameter_name,
                created_at=timezone.now(),
            ))

        self.bulk_manager.done(log_prefix=self.log_prefix)

        self.update_caches_from_db('parameters', DictParameter, 'name')

    def update_sku_cache(self, retrieved):
        self.update_caches_from_db('skus', Sku, 'article')

        for sku_article in self.filter_items_not_found('skus', Sku, 'article'):
            if len(self.brands_cache.keys()) > 0 and retrieved[sku_article]['brand'] is not None:
                brand_id = self.brands_cache[retrieved[sku_article]['brand']]
            else:
                brand_id = None

            self.bulk_manager.add(Sku(
                marketplace_id=retrieved[sku_article]['marketplace'],
                article=retrieved[sku_article]['article'],
                url=retrieved[sku_article]['url'],
                title=retrieved[sku_article]['title'],
                brand_id=brand_id,
                created_at=timezone.now(),
                updated_at=timezone.now(),
            ))

        self.bulk_manager.done(log_prefix=self.log_prefix)

        self.update_caches_from_db('skus', Sku, 'article')


def guess_wb_article(item):
    if len(str(item['wb_id'])) > 20:
        return re.findall(r'\/catalog\/(\d{1,20})\/detail\.aspx', item['product_url'])[0]
    else:
        return item['wb_id']
