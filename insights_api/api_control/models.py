from __future__ import unicode_literals

from django.db import models


class ProductList(models.Model):
    id = models.IntegerField(primary_key=True)
    user_id = models.IntegerField()
    name = models.CharField(max_length=250)
    crawl = models.NullBooleanField()
    created_at = models.DateTimeField(blank=True, null=True)
    is_public = models.NullBooleanField()
    with_price = models.NullBooleanField()
    urgent = models.NullBooleanField()
    is_custom_filter = models.NullBooleanField()
    crawl_frequency = models.TextField(blank=True, null=True)
    type = models.TextField()
    ignore_variant_data = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'product_list'


class SearchTerms(models.Model):
    id = models.IntegerField(primary_key=True)
    title = models.TextField(blank=True, null=True)
    group_id = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'search_terms'

class SearchTermsGroups(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.TextField()
    created_at = models.DateTimeField(blank=True, null=True)
    enabled = models.NullBooleanField()

    class Meta:
        managed = False
        db_table = 'search_terms_groups'

class Sites(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=256)
    url = models.CharField(max_length=255)
    image_url = models.TextField()
    site_type = models.IntegerField()
    results_per_page = models.IntegerField(blank=True, null=True)
    zip_code = models.IntegerField(blank=True, null=True)
    traffic_upload = models.NullBooleanField()
    crawler_name = models.TextField(blank=True, null=True)
    location = models.TextField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sites'


class GroupsSites(models.Model):
    group_id = models.ForeignKey(SearchTerms, models.DO_NOTHING, db_column='group_id')
    site_id = models.ForeignKey(Sites, models.DO_NOTHING, db_column='site_id')

    class Meta:
        managed = False
        db_table = 'groups_sites'


class ProductListResultsSummary(models.Model):
    id = models.IntegerField(primary_key=True)
    product_list = models.ForeignKey(ProductList, models.DO_NOTHING)
    site = models.ForeignKey('Sites', models.DO_NOTHING, blank=True, null=True)
    date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'product_list_results_summary'


class SearchTermsBrandsRelation(models.Model):
    id = models.IntegerField(primary_key=True)
    search_term_id = models.ForeignKey(SearchTerms, models.DO_NOTHING, db_column='search_term_id')
    brand_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'search_terms_brands_relation'

class RankingSearchResultsItemsSummary(models.Model):
    id = models.IntegerField(primary_key=True)
    site_id = models.IntegerField()
    total_results = models.IntegerField(blank=True, null=True)
    brand_results = models.IntegerField(blank=True, null=True)
    search_items_brands_relation_id = models.IntegerField()
    date_of_upload = models.DateField(blank=True, null=True)
    on_first_page = models.TextField()

    class Meta:
        managed = False
        db_table = 'ranking_search_results_items_summary'


class RankingSearchResultsItems(models.Model):
    site_id = models.IntegerField()
    search_items_brands_relation_id = models.ForeignKey(SearchTermsBrandsRelation, models.DO_NOTHING)
    date_of_upload = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ranking_search_results_items'


class Date(models.Model):
    date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False

class BrandTypes(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'brand_types'


class Brands(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    image_url = models.TextField()

    class Meta:
        managed = False
        db_table = 'ranking_brands'


class PriceData(models.Model):
    search_term = models.TextField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, null=True)
    price = models.DecimalField(max_digits=17, decimal_places=2, blank=True, null=True)
    
    class Meta:
        managed = False

class RankingData(models.Model):
    search_term = models.TextField(blank=True, null=True)
    site_id = models.IntegerField()
    title = models.TextField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    ranking = models.IntegerField()

    class Meta:
        managed = False

class OutOfStockData(models.Model):
    search_term = models.TextField(blank=True, null=True)
    site_id = models.IntegerField(blank=True)
    title = models.TextField(blank=True, null=True)
    url = models.TextField(blank=True, null=True)
    is_out_of_stock = models.BooleanField()
    no_longer_available = models.NullBooleanField()

    class Meta:
        managed = False

class BuyBoxData(models.Model):
    search_term = models.TextField(blank=True, null=True)
    site_id = models.IntegerField(blank=True)
    title = models.TextField(blank=True, null=True)
    marketplace = models.CharField(max_length=250)
    url = models.TextField(blank=True, null=True)
    is_out_of_stock = models.BooleanField()
    no_longer_available = models.NullBooleanField()
    first_party_owned = models.NullBooleanField()

    class Meta:
        managed = False

class ReviewData(models.Model):
    search_term = models.TextField(blank=True, null=True)
    site_id = models.IntegerField(blank=True)
    url = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    total_count = models.IntegerField()
    average_num = models.FloatField()
    one_star = models.IntegerField()
    two_star = models.IntegerField()
    three_star = models.IntegerField()
    four_star = models.IntegerField()
    five_star = models.IntegerField()

    class Meta:
        managed = False
