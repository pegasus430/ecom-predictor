import models
from rest_framework import serializers


class ProductListSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.ProductList
        fields = ('id', 'user_id', 'name', 'crawl', 'created_at', 'is_public',
                  'with_price', 'urgent', 'is_custom_filter',
                  'crawl_frequency', 'type', 'ignore_variant_data')


class DatesSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Date
        fields = ('date',)


class SearchTermsSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.SearchTerms
        fields = ('id', 'title', 'group_id')


class SearchTermsGroupsSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.SearchTermsGroups
        fields = ('id', 'name', 'created_at', 'enabled')


class SitesSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Sites
        fields = ('id', 'name', 'url', 'image_url', 'site_type',
                  'results_per_page', 'zip_code', 'traffic_upload',
                  'crawler_name', 'location', 'user_agent')


class BrandsSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Brands
        fields = ('id', 'name', 'image_url')
        depth = 1

class PriceDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.PriceData
        fields = ('search_term', 'url', 'title', 'currency', 'price')

class RankingDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.RankingData
        fields = ('search_term', 'site_id', 'title', 'url', 'ranking')

class OutOfStockDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.OutOfStockData
        fields = ('search_term', 'site_id', 'title', 'url', 'is_out_of_stock',
                  'no_longer_available')

class BuyBoxDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.BuyBoxData
        fields = ('search_term', 'site_id', 'title', 'marketplace', 'url',
                  'is_out_of_stock', 'no_longer_available',
                  'first_party_owned')

class ReviewDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.ReviewData
        fields = ('search_term', 'site_id', 'url', 'title', 'total_count',
                  'average_num', 'one_star', 'two_star', 'three_star',
                  'four_star', 'five_star')
