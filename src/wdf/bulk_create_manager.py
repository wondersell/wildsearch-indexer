import logging
import psycopg2
import re
import time
from collections import defaultdict
from csv import DictWriter
from django.apps import apps
from django.db import connection, models
from io import StringIO

logger = logging.getLogger('wdf.indexer')
logger.setLevel(logging.INFO)


class BulkCreateManager(object):
    """
    Приблуда для сбора объектов Django ORM и пакетной загрузки их в БД через COPY FROM Посгреса или bulk_create Джанги
    с учетом их ограничений. Автоматически разбивает объекты на очереди в зависимости от их типа. Новый объект
    добавляется методом add(), загрузка происходит после вызова метода done(). Метод done() сохраняет записи из
    всех очередей.

    Переделанная и доработанная версия из статьи https://www.caktusgroup.com/blog/2019/01/09/django-bulk-inserts/
    """

    def __init__(self, max_chunk_size=None, copy_safe_models=()):
        self._copy_safe_models = copy_safe_models
        self._max_chunk_size = max_chunk_size

        self._pg_copy_create_queues = defaultdict(list)
        self._bulk_create_queues = defaultdict(list)

        self.log_prefix = ''

    def add(self, obj):
        """
        Добавление объекта в список на пакетную загрузку
        """
        model_class = type(obj)
        model_key = model_class._meta.label
        self._pg_copy_create_queues[model_key].append(obj)

    def done(self, log_prefix=''):
        """
        Пакетная загрузка всех объектов из всех списков
        """
        self.log_prefix = log_prefix

        for model_name, objects in self._pg_copy_create_queues.items():
            if len(objects) > 0:
                self._commit(apps.get_model(model_name))

    def _commit(self, model_class):
        """
        Определение что каким методом будем загружать
        """
        model_key = model_class._meta.label

        has_text_fields = self._check_for_text_fields(model_class)
        has_cursor = self._check_for_cursor()

        if has_text_fields is True or has_cursor is False:
            self._move_to_bulk_create(model_class)

        if len(self._pg_copy_create_queues[model_key]) > 0:
            self._commit_pg_copy(model_class)

            self._pg_copy_create_queues[model_key] = []

        if len(self._bulk_create_queues[model_key]) > 0:
            self._commit_bulk_create(model_class)

            self._bulk_create_queues[model_key] = []

    def _commit_pg_copy(self, model_class):
        """
        Алгоритм загрузки через команду COPY FROM Постгреса с возможностью фоллбэка на bulk_create,
        если что-то пошло не так
        """
        model_key = model_class._meta.label

        slices = self._split_in_slices(self._pg_copy_create_queues[model_key])

        chunk_no = 1

        for _slice in slices:
            export_file, header = self._prepare_export_csv_with_headers(_slice, model_class)

            cursor = connection.cursor()

            try:
                start_time = time.time()

                cursor.copy_from(export_file, model_class._meta.db_table, sep='\t', null='', columns=header)

                connection.commit()

                time_spent = time.time() - start_time

                logger.info(
                    f'{self.log_prefix}(chunk {chunk_no}/{len(slices)}) {model_key} dump saved via PG COPY ({len(_slice)} items) in {time_spent}s, {round(len(_slice) / time_spent * 60)} items/min')
            except psycopg2.DatabaseError as error:
                """
                Иногда у COPY не получается импортировать какую-то строчку просто потому что иди нахуй, вот почему.
                В этом случае исключаем строку на импорт с COPY и пробуем еще раз. Исключенные строки потом попробуем
                импортировать через bulk_create (обычно помогает)
                """
                line_number = int(re.findall(r'line (\d+)', str(error))[0])

                logger.error(
                    f'{self.log_prefix}Copy to table {model_class._meta.db_table} failed for row {line_number}: {self._pg_copy_create_queues[model_key][line_number - 1].__dict__}')

                self._bulk_create_queues[model_key].append(self._pg_copy_create_queues[model_key].pop(line_number - 1))

                logger.info(f'{self.log_prefix}Retrying COPY to table {model_class._meta.db_table} without problem row')

                connection.rollback()

                cursor.close()

                self._commit(model_class)
            else:
                cursor.close()

            chunk_no += 1

    def _commit_bulk_create(self, model_class):
        """
        Алгоритм загрузки через bulk_create из Django ORM
        """
        model_key = model_class._meta.label

        slices = self._split_in_slices(self._bulk_create_queues[model_key])

        chunk_no = 1

        for _slice in slices:
            start_time = time.time()

            model_class.objects.bulk_create(_slice)

            time_spent = time.time() - start_time

            logger.info(
                f'{self.log_prefix}(slice {chunk_no}/{len(slices)}) {model_key} dump saved via bulk_create ({len(_slice)} items) in {time_spent}s, {round(len(_slice) / time_spent * 60)} items/min')

            chunk_no += 1

    def _prepare_export_csv_with_headers(self, chunk, model_class):
        """
        Подготовка CSV массива данных для COPY FROM
        """
        model_key = model_class._meta.label

        start_time = time.time()

        items_count = len(chunk)

        csv_data = StringIO()

        header = [field.column for field in model_class._meta.fields]

        writer = DictWriter(csv_data, fieldnames=header, delimiter='\t')

        for item in chunk:
            item_data = item.__dict__.copy()

            if '_state' in item_data.keys():
                del item_data['_state']

            writer.writerow(item_data)

        csv_data.seek(0)

        time_spent = time.time() - start_time

        logger.info(
            f'{self.log_prefix}{model_key} dump prepared for PG COPY ({items_count} items) in {time_spent}s, {round(items_count / time_spent * 60)} items/min')

        return csv_data, header

    def _check_for_text_fields(self, model_class):
        """
        Если в модели есть текстовые поля, то с большой вероятностью COPY их импортирует криво, нужно переключаться
        в режим bulk_create
        """
        model_key = model_class._meta.label

        if model_key in self._copy_safe_models:
            return False

        for field in model_class._meta.get_fields():
            if isinstance(field, models.CharField):
                logger.info(
                    f'{self.log_prefix}Detected text field in model {model_key}, using bulk create instead of PG COPY')

                return True

        return False

    def _check_for_cursor(self):
        """
        На тестовых средах у нас может не быть постгреса и copy_from. В этом случае тоже нужен фоллбэк
        """
        return hasattr(connection.cursor(), 'copy_from')

    def _move_to_bulk_create(self, model_class):
        """
        Перемещение всех записей из очереди на загрузку через COPY FROM в очредь на загрузку через bulk_create
        """
        model_key = model_class._meta.label

        self._bulk_create_queues[model_key] = self._pg_copy_create_queues[model_key].copy()

        self._pg_copy_create_queues[model_key] = []

    def _split_in_slices(self, queue):
        """
        Разбивает массив на несколько частей так, чтобы в каждой части было не больше _max_chunk_size объектов
        """

        return [queue[i:i + self._max_chunk_size] for i in range(0, len(queue), self._max_chunk_size)]
