import uuid

from django.db import models


class Dump(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    crawler = models.CharField(max_length=20)
    job = models.CharField(max_length=20)
    crawl_started_at = models.DateTimeField()
    crawl_ended_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dump'
        ordering = ['created_at']

    def __str__(self):
        return f'Dump #{self.pk}'


class Version(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    dump = models.ForeignKey('Dump', on_delete=models.CASCADE, null=True)
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
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
    marketplace = models.ForeignKey('DictMarketplace', on_delete=models.CASCADE)
    brand = models.ForeignKey('DictBrand', on_delete=models.CASCADE)
    article = models.CharField(max_length=20)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wdf_sku'
        ordering = ['created_at']

    def __str__(self):
        return f'Sku #{self.pk}'


class Price(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE)
    price = models.FloatField()
    price_dirty = models.FloatField(null=True)
    discount = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_price'
        ordering = ['created_at']

    def __str__(self):
        return f'Price #{self.pk}'


class Rating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE)
    rating = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_rating'
        ordering = ['created_at']

    def __str__(self):
        return f'Rating #{self.pk}'


class Sales(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE)
    sales = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_sales'
        ordering = ['created_at']

    def __str__(self):
        return f'Sales counter #{self.pk}'


class Position(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE)
    catalog = models.ForeignKey('DictCatalog', on_delete=models.CASCADE)
    absolute = models.PositiveIntegerField()
    percintile = models.FloatField(null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_position'
        ordering = ['created_at']

    def __str__(self):
        return f'Position #{self.pk}'


class Seller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    seller = models.ForeignKey('DictSeller', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_seller'
        ordering = ['created_at']

    def __str__(self):
        return f'Seller #{self.pk}'


class Reviews(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE)
    reviews = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_reviews'
        ordering = ['created_at']

    def __str__(self):
        return f'Reviews counter #{self.pk}'


class Parameter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    sku = models.ForeignKey('Sku', on_delete=models.CASCADE)
    version = models.ForeignKey('Version', on_delete=models.CASCADE)
    parameter = models.ForeignKey('DictParameter', on_delete=models.CASCADE)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_parameter'
        ordering = ['created_at']

    def __str__(self):
        return f'Parameter #{self.pk}'


class DictMarketplace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # noqa: VNE003
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dict_marketplace'
        ordering = ['created_at']

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
    name = models.CharField(max_length=255, null=True, default=None)
    url = models.URLField()
    level = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wdf_dict_catalog'
        ordering = ['created_at']

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

    def __str__(self):
        return f'Parameter dictionary #{self.pk}'
