import time
from datetime import datetime

import pytz
from dateutil.parser import parse as date_parse
from django.conf import settings
from scrapinghub import ScrapinghubClient

from wdf.models import (
    DictBrand, DictCatalog, DictMarketplace, DictParameter, Dump, Parameter, Price, Rating, Reviews, Sales, Sku,
    Version)


class Indexer(object):
    def __init__(self, stdout=None, style=None):
        self.stdout = stdout
        self.style = style

        self.marketplace_model = None
        self.dump_model = None
        self.sh_client = None
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
        """

        spider_slug = 'wb'

        if Dump.objects.filter(job=job_id).count() > 0:
            if self.stdout is not None:
                self.stdout.write(self.style.SUCCESS(
                    f'Dump for job {job_id} already exists, skipping'))

            return

        self.sh_client = self.get_sh_client()
        self.generator = self.get_generator(job_id=job_id, chunk_size=chunk_size)
        self.marketplace_model = self.get_marketplace_model(spider_slug)
        self.dump_model = self.get_dump_model(spider_slug, job_id)

        chunk_no = 1
        for chunk in self.generator:
            start_time = time.time()

            self.clear_collections()

            for item in chunk:
                self.collect_wb_catalogs(item)
                self.collect_wb_brands(item)
                self.collect_wb_parameters(item)
                self.collect_wb_skus(item)

            self.update_brands_cache(self.catalogs)
            self.update_brands_cache(self.brands)
            self.update_parameters_cache(self.parameters)
            self.update_sku_cache(self.skus)

            # Записываем версии для каждого артикула
            for item in chunk:
                version = self.save_version(item)

                self.save_price(version, item)
                self.save_rating(version, item)
                self.save_sales(version, item)
                self.save_reviews(version, item)
                self.save_parameters(version, item)

            time_spent = time.time() - start_time

            if self.stdout is not None:
                self.stdout.write(self.style.SUCCESS(
                    f'Chunk #{chunk_no} processed in {time_spent}s, {round(len(chunk) / time_spent * 60)} items/min'))

            chunk_no += 1

    @staticmethod
    def get_sh_client():
        client_key = settings.SH_APIKEY

        return ScrapinghubClient(client_key)

    def get_generator(self, job_id, chunk_size=500):
        return self.sh_client.get_job(job_id).items.list_iter(chunksize=chunk_size)

    @staticmethod
    def get_marketplace_model(spider_slug):
        try:
            marketplace_model = DictMarketplace.objects.get(slug=spider_slug)
        except DictMarketplace.DoesNotExist:
            marketplace_model = DictMarketplace(name=spider_slug, slug=spider_slug)

            marketplace_model.save()

        return marketplace_model

    def get_dump_model(self, spider_slug, job_id):
        job_metadata = self.sh_client.get_job(job_id).metadata

        dump_model = Dump(
            crawler=spider_slug,
            job=job_id,
            crawl_started_at=pytz.utc.localize(datetime.fromtimestamp(job_metadata.get('running_time') / 1000)),
            crawl_ended_at=pytz.utc.localize(datetime.fromtimestamp(job_metadata.get('finished_time') / 1000)),
        )

        dump_model.save()

        return dump_model

    def save_version(self, item):
        version = Version(
            dump=self.dump_model,
            sku_id=self.sku_cache[item['wb_id']],
            crawled_at=pytz.utc.localize(date_parse(item['parse_date'])),
        )

        version.save()

        return version

    def save_price(self, version, item):
        if 'wb_price' in item.keys():
            Price(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                price=float(item['wb_price']),
            ).save()

    def save_rating(self, version, item):
        if 'wb_rating' in item.keys():
            Rating(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                rating=item['wb_rating'],
            ).save()

    def save_sales(self, version, item):
        if 'wb_purchases_count' in item.keys():
            Sales(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                sales=item['wb_purchases_count'],
            ).save()

    def save_reviews(self, version, item):
        if 'wb_reviews_count' in item.keys():
            Reviews(
                sku_id=self.sku_cache[item['wb_id']],
                version=version,
                reviews=item['wb_reviews_count'],
            ).save()

    def save_parameters(self, version, item):
        if 'features' in item.keys():
            for feature_name, feature_value in item['features'][0].items():
                Parameter(
                    sku_id=self.sku_cache[item['wb_id']],
                    version=version,
                    parameter_id=self.parameter_cache[feature_name],
                    value=feature_value,
                ).save()

    def clear_collections(self):
        self.catalogs = {}
        self.brands = {}
        self.parameters = {}
        self.skus = {}

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

    def update_catalogs_cache(self, retrieved):
        catalogs_to_retrieve = set(retrieved.keys()).difference(set(self.catalog_cache.keys()))
        catalogs_retrieved = DictCatalog.objects.filter(url__in=catalogs_to_retrieve)
        self.catalog_cache = {**self.catalog_cache, **dict([(item.url, item.id) for item in catalogs_retrieved])}
        catalogs_not_found = set(retrieved.keys()).difference(set(self.catalog_cache.keys()))

        for catalog_url in catalogs_not_found:
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
        brands_to_retrieve = set(retrieved.keys()).difference(set(self.brand_cache.keys()))
        brands_retrieved = DictBrand.objects.filter(url__in=brands_to_retrieve)
        self.brand_cache = {**self.brand_cache, **dict([(item.url, item.id) for item in brands_retrieved])}
        brands_not_found = set(retrieved.keys()).difference(set(self.brand_cache.keys()))

        for brand_url in brands_not_found:
            new_model = DictBrand(
                marketplace_id=retrieved[brand_url]['marketplace'],
                name=retrieved[brand_url]['name'],
                url=retrieved[brand_url]['url'],
            )

            new_model.save()

            self.brand_cache[brand_url] = new_model.id

    def update_parameters_cache(self, retrieved):
        parameters_to_retrieve = set(retrieved.keys()).difference(set(self.parameter_cache.keys()))
        parameters_retrieved = DictParameter.objects.filter(name__in=parameters_to_retrieve)
        self.parameter_cache = {**self.parameter_cache, **dict([(item.name, item.id) for item in parameters_retrieved])}
        parameters_not_found = set(retrieved.keys()).difference(set(self.parameter_cache.keys()))

        for parameter_name in parameters_not_found:
            new_model = DictParameter(
                marketplace_id=retrieved[parameter_name]['marketplace'],
                name=parameter_name,
            )

            new_model.save()

            self.parameter_cache[parameter_name] = new_model.id

    def update_sku_cache(self, retrieved):
        skus_to_retrieve = set(retrieved.keys()).difference(set(self.sku_cache.keys()))
        skus_retirieved = Sku.objects.filter(article__in=skus_to_retrieve)
        self.sku_cache = {**self.sku_cache, **dict([(item.article, item.id) for item in skus_retirieved])}
        skus_not_found = set(retrieved.keys()).difference(set(self.sku_cache.keys()))

        for sku_article in skus_not_found:
            new_model = Sku(
                marketplace_id=retrieved[sku_article]['marketplace'],
                brand_id=self.brand_cache[retrieved[sku_article]['brand']],
                article=retrieved[sku_article]['article'],
                url=retrieved[sku_article]['url'],
                title=retrieved[sku_article]['title'],
            )

            new_model.save()

            self.sku_cache[sku_article] = new_model.id
