import uuid
from django.db import connection, models


class Dump(models.Model):
    ERROR = -1
    CREATED = 0
    PREPARING = 5
    PREPARED = 10
    SCHEDULING = 15
    SCHEDULED = 20
    PROCESSING = 25
    PROCESSED = 30

    State_codes = (
        (ERROR, 'Error'),
        (CREATED, 'Created'),
        (PREPARING, 'Preparing'),
        (PREPARED, 'Prepared'),
        (SCHEDULING, 'Scheduling'),
        (SCHEDULED, 'Scheduled'),
        (PROCESSING, 'Processing'),
        (PROCESSED, 'Processed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    crawler = models.CharField(max_length=20)
    job = models.CharField(max_length=20)
    job_type = models.CharField(max_length=20, blank=True, default='')
    state = models.CharField(max_length=20, blank=True, default='created')
    state_code = models.IntegerField(choices=State_codes, default=CREATED)
    items_crawled = models.IntegerField(null=True)
    crawl_started_at = models.DateTimeField(null=True)
    crawl_ended_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_state(self, state_code):
        self.state_code = state_code
        self.state = [item[1] for item in self.State_codes if item[0] == state_code][0].lower()

    def prune(self):
        with connection.cursor() as cursor:
            cursor.execute(
                'DELETE FROM wdf_parameter WHERE version_id IN (SELECT id FROM wdf_version WHERE dump_id=%s);',
                [self.id])

            cursor.execute(
                'DELETE FROM wdf_position WHERE version_id IN (SELECT id FROM wdf_version WHERE dump_id=%s);',
                [self.id])

            cursor.execute(
                'DELETE FROM wdf_price WHERE version_id IN (SELECT id FROM wdf_version WHERE dump_id=%s);',
                [self.id])

            cursor.execute(
                'DELETE FROM wdf_rating WHERE version_id IN (SELECT id FROM wdf_version WHERE dump_id=%s);',
                [self.id])

            cursor.execute(
                'DELETE FROM wdf_reviews WHERE version_id IN (SELECT id FROM wdf_version WHERE dump_id=%s);',
                [self.id])

            cursor.execute(
                'DELETE FROM wdf_sales WHERE version_id IN (SELECT id FROM wdf_version WHERE dump_id=%s);',
                [self.id])

            cursor.execute('DELETE FROM wdf_version WHERE dump_id=%s;', [self.id])

        return self.delete()

    def get_versions_num(self):
        return Version.objects.filter(dump_id=self.id).count()

    class Meta:
        db_table = 'wdf_dump'
        ordering = ['created_at']

    def __str__(self):
        return f'Dump #{self.pk}'


class Version(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    dump = models.ForeignKey('Dump', on_delete=models.CASCADE, null=True)
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE, null=True)
    catalog_level = models.IntegerField(null=True)
    crawled_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_version'
        ordering = ['created_at']

    def __str__(self):
        return f'Version #{self.pk}'


class Sku(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    title = models.CharField(max_length=512)
    marketplace = models.ForeignKey('DictMarketplace', on_delete=models.CASCADE, null=True)
    brand = models.ForeignKey('DictBrand', on_delete=models.CASCADE, null=True, default=None)
    article = models.CharField(max_length=20)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def merge_duplicates(self):
        with connection.cursor() as cursor:
            cursor.execute('UPDATE wdf_parameter SET sku_id=%s WHERE sku_id IN (SELECT id FROM wdf_sku WHERE article=%s AND id!=%s);', [self.id, self.article, self.id])
            cursor.execute('UPDATE wdf_position SET sku_id=%s WHERE sku_id IN (SELECT id FROM wdf_sku WHERE article=%s AND id!=%s);', [self.id, self.article, self.id])
            cursor.execute('UPDATE wdf_price SET sku_id=%s WHERE sku_id IN (SELECT id FROM wdf_sku WHERE article=%s AND id!=%s);', [self.id, self.article, self.id])
            cursor.execute('UPDATE wdf_rating SET sku_id=%s WHERE sku_id IN (SELECT id FROM wdf_sku WHERE article=%s AND id!=%s);', [self.id, self.article, self.id])
            cursor.execute('UPDATE wdf_reviews SET sku_id=%s WHERE sku_id IN (SELECT id FROM wdf_sku WHERE article=%s AND id!=%s);', [self.id, self.article, self.id])
            cursor.execute('UPDATE wdf_sales SET sku_id=%s WHERE sku_id IN (SELECT id FROM wdf_sku WHERE article=%s AND id!=%s);', [self.id, self.article, self.id])
            cursor.execute('UPDATE wdf_version SET sku_id=%s WHERE sku_id IN (SELECT id FROM wdf_sku WHERE article=%s AND id!=%s);', [self.id, self.article, self.id])
            cursor.execute('DELETE FROM wdf_sku WHERE article=%s AND id!=%s;', [self.article, self.id])

            return True

    class Meta:
        db_table = 'wdf_sku'
        ordering = ['created_at']

        indexes = [
            models.Index(fields=['article']),
        ]

    def __str__(self):
        return f'Sku #{self.pk}'


class Price(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE, null=True)
    version = models.ForeignKey('Version', on_delete=models.CASCADE, null=True)
    price = models.FloatField()
    price_dirty = models.FloatField(null=True)
    discount = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_price'
        ordering = ['created_at']

        constraints = [
            models.UniqueConstraint(fields=['sku', 'version'], name='unique_price_version'),
        ]

    def __str__(self):
        return f'Price #{self.pk}'


class Rating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE, null=True)
    version = models.ForeignKey('Version', on_delete=models.CASCADE, null=True)
    rating = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_rating'
        ordering = ['created_at']

        constraints = [
            models.UniqueConstraint(fields=['sku', 'version'], name='unique_rating_version'),
        ]

    def __str__(self):
        return f'Rating #{self.pk}'


class Sales(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE, null=True)
    version = models.ForeignKey('Version', on_delete=models.CASCADE, null=True)
    sales = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_sales'
        ordering = ['created_at']

        constraints = [
            models.UniqueConstraint(fields=['sku', 'version'], name='unique_sales_version'),
        ]

    def __str__(self):
        return f'Sales counter #{self.pk}'


class Position(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE, null=True)
    catalog = models.ForeignKey('DictCatalog', on_delete=models.CASCADE, null=True)
    absolute = models.PositiveIntegerField(null=True)
    percintile = models.FloatField(null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_position'
        ordering = ['created_at']

        constraints = [
            models.UniqueConstraint(fields=['sku', 'version', 'catalog'], name='unique_position_catalog_version'),
        ]

    def __str__(self):
        return f'Position #{self.pk}'


class Seller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE, null=True)
    seller = models.ForeignKey('DictSeller', on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_seller'
        ordering = ['created_at']

    def __str__(self):
        return f'Seller #{self.pk}'


class Reviews(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE, null=True)
    version = models.ForeignKey('Version', on_delete=models.CASCADE, null=True)
    reviews = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_reviews'
        ordering = ['created_at']

        constraints = [
            models.UniqueConstraint(fields=['sku', 'version'], name='unique_reviews_version'),
        ]

    def __str__(self):
        return f'Reviews counter #{self.pk}'


class Parameter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE, null=True)
    version = models.ForeignKey('Version', on_delete=models.CASCADE, null=True)
    parameter = models.ForeignKey('DictParameter', on_delete=models.CASCADE, null=True)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_parameter'
        ordering = ['created_at']

        constraints = [
            models.UniqueConstraint(fields=['sku', 'version', 'parameter'], name='unique_parameter_version'),
        ]

    def __str__(self):
        return f'Parameter #{self.pk}'


class DictMarketplace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dict_marketplace'
        ordering = ['created_at']

        constraints = [
            models.UniqueConstraint(fields=['name', 'slug'], name='unique_marketplace_name_slug'),
        ]

    def __str__(self):
        return f'Marketplace dictionary item #{self.pk}'


class DictBrand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    marketplace = models.ForeignKey('DictMarketplace', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dict_brand'
        ordering = ['created_at']

        indexes = [
            models.Index(fields=['url']),
        ]

    def __str__(self):
        return f'Brand dictionary item #{self.pk}'


class DictSeller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    marketplace = models.ForeignKey('DictMarketplace', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dict_seller'
        ordering = ['created_at']

    def __str__(self):
        return f'Seller dictionary #{self.pk}'


class DictCatalog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    marketplace = models.ForeignKey('DictMarketplace', on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, default=None)
    name = models.TextField(null=True)  # noqa: DJ01
    url = models.URLField()
    level = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dict_catalog'
        ordering = ['created_at']

        indexes = [
            models.Index(fields=['url']),
        ]

    def __str__(self):
        return f'Catalog dictionary #{self.pk}'


class DictParameter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    marketplace = models.ForeignKey('DictMarketplace', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dict_parameter'
        ordering = ['created_at']

        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f'Parameter dictionary #{self.pk}'
