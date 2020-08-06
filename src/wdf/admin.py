from django.contrib import admin

from wdf.models import (
    DictBrand, DictCatalog, DictMarketplace, DictParameter, DictSeller, Dump, Parameter, Position, Price, Rating,
    Reviews, Sales, Seller, Sku, Version)

admin.site.register(Dump)
admin.site.register(Version)
admin.site.register(Sku)
admin.site.register(Price)
admin.site.register(Rating)
admin.site.register(Sales)
admin.site.register(Position)
admin.site.register(Seller)
admin.site.register(Reviews)
admin.site.register(Parameter)
admin.site.register(DictMarketplace)
admin.site.register(DictBrand)
admin.site.register(DictSeller)
admin.site.register(DictCatalog)
admin.site.register(DictParameter)
