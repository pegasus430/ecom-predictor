import re
import django_filters

from django.db import connection
from rest_framework import viewsets, filters

from models import ProductList, Sites, SearchTerms,\
    Brands, SearchTermsGroups

from serializers import ProductListSerializer, DatesSerializer,\
    SearchTermsSerializer, SitesSerializer, BrandsSerializer,\
    SearchTermsGroupsSerializer, PriceDataSerializer, RankingDataSerializer, \
    OutOfStockDataSerializer, BuyBoxDataSerializer, ReviewDataSerializer

from exceptions import ParamsCombinationError, FormatDaterror,\
    ParamNotSupportedError, MissingParamError


def get_range(range_str):
    if '-' in range_str:
        endpoints = range_str.split('-')
        return (endpoints[0], endpoints[1])


# ViewSets define the view behavior.
class ProductListViewSet(viewsets.ModelViewSet):
    #queryset = ProductList.objects.all()
    serializer_class = ProductListSerializer
    http_method_names = ['get']

    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('user_id', 'name', 'crawl', 'created_at', 'is_public',
                     'with_price', 'urgent', 'is_custom_filter',
                     'crawl_frequency', 'type', 'ignore_variant_data')

    def get_queryset(self):
        product_list_id = self.request.query_params.get('id', None)

        if product_list_id:
            if '-' in product_list_id:
                return ProductList.objects.filter(id__range = get_range(product_list_id))
            return ProductList.objects.filter(id__in = product_list_id.split(','))

        return ProductList.objects.all()

class SearchTermsViewSet(viewsets.ModelViewSet):
    #queryset = SearchTerms.objects.all()
    serializer_class = SearchTermsSerializer
    http_method_names = ['get']

    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('title', 'group_id')

    def get_queryset(self):
        search_terms_id = self.request.query_params.get('id', None)

        if search_terms_id:
            if '-' in search_terms_id:
                return SearchTerms.objects.filter(id__range = get_range(search_terms_id))
            return SearchTerms.objects.filter(id__in = search_terms_id.split(','))

        return SearchTerms.objects.all()

class SearchTermsGroupsViewSet(viewsets.ModelViewSet):
    #queryset = SearchTermsGroups.objects.all()
    serializer_class = SearchTermsGroupsSerializer
    http_method_names = ['get']

    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('name', 'created_at', 'enabled')

    def get_queryset(self):
        search_terms_groups_id = self.request.query_params.get('id', None)

        if search_terms_groups_id:
            if '-' in search_terms_groups_id:
                return SearchTermsGroups.objects.filter(id__range = get_range(search_terms_groups_id))
            return SearchTermsGroups.objects.filter(id__in = search_terms_groups_id.split(','))

        return SearchTermsGroups.objects.all()


def format_range(range_str):
    if '-' in range_str:
        return 'between %s and %s' % get_range(range_str)

    return 'in (%s)' % range_str

def checkAndFormatDates(dates):
    if not dates:
        return

    is_range = False

    if len(dates.split('-')) == 6:
        is_range = True

        date1 = '-'.join(dates.split('-')[:3])
        date2 = '-'.join(dates.split('-')[3:])
        dates = [date1, date2]
    else:
        dates = dates.split(',')

    # Check if date format is "YYYY-MM-DD"
    for date in dates:
        if not re.match('^\d{4}-(0?[1-9]|1[0-2])-(0?[1-9]|1\d|2\d|3[0-1])$', date):
            raise FormatDaterror()

    if is_range:
        return "between '%s' and '%s'" % (dates[0], dates[1])

    return 'in (%s)' % ','.join(map(lambda d: "'%s'" % d, dates))


# ViewSets define the view behavior.
class SitesViewSet(viewsets.ModelViewSet):
    serializer_class = SitesSerializer
    http_method_names = ['get']

    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'name', 'url', 'image_url', 'site_type',
                     'results_per_page', 'zip_code', 'traffic_upload',
                     'crawler_name', 'location', 'user_agent')

    def get_queryset(self):
        request = self.request
        product_list_id = request.query_params.get('product_list_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        search_term_group_id = request.query_params.get('search_term_group_id', None)
        date = request.query_params.get('date', None)
        waiting = request.query_params.get('waiting', None)

        date = checkAndFormatDates(date)

        # Check if more than 1 param from the this have been set
        if len(filter(None, [product_list_id, search_term_id, search_term_group_id])) > 1:
            raise ParamsCombinationError()

        sql_query = None

        if product_list_id:
            # Product List ID and Date
            if date:
                sql_query = """
                            select distinct s.* from sites s
                            join product_list_results_summary plrs on plrs.site_id = s.id
                            where s.site_type = 1 and plrs.product_list_id {product_list_id} and plrs.date {date};
                            """.format(product_list_id = format_range(product_list_id),
                                date=date)

            else:
                sql_query = """
                        select distinct s.* from sites s
                        join product_list_results_summary plrs on plrs.site_id = s.id
                        where s.site_type = 1 and plrs.product_list_id {product_list_id};
                        """.format(product_list_id = format_range(product_list_id))

        if search_term_id:
            # Search Term ID and Date
            if date:
                raise ParamNotSupportedError('Date filter for Search Term '
                                             'Id is not implemented yet')

            # Search Term ID
            else:
                sql_query = """
                            select s.* from sites s
                            join groups_sites gs on gs.site_id = s.id
                            join search_terms st on st.group_id = gs.group_id
                            where s.site_type = 1 and st.id {search_term_id};
                            """.format(search_term_id = format_range(search_term_id))

        if search_term_group_id:
            # Search Term Group ID and Date
            if waiting:
                # For a given search term group, tell which sites are currently set to be crawled
                sql_query = """
                    select s.* from sites s
                    join groups_sites gs on gs.site_id = s.id
                    where s.site_type = 1 and gs.group_id {search_term_group_id};
                    """.format(search_term_group_id = format_range(search_term_group_id))

            elif date:
                # For a given search term group, tell which sites were crawled on a given date
                sql_query = """
                            select distinct s.* from sites s
                            join ranking_search_results_items_summary rsris on rsris.site_id = s.id
                            join search_terms_brands_relation stbr on stbr.id = rsris.search_items_brands_relation_id
                            join search_terms st on st.id = stbr.search_term_id
                            where st.group_id {search_term_group_id} and rsris.date_of_upload {date};
                            """.format(search_term_group_id = format_range(search_term_group_id),
                                date=date)
            else:
                # Search Term Group ID
                sql_query = """
                            select distinct s.* from sites s
                            join ranking_search_results_items_summary rsris on rsris.site_id = s.id
                            join search_terms_brands_relation stbr on stbr.id = rsris.search_items_brands_relation_id
                            join search_terms st on st.id = stbr.search_term_id
                            where st.group_id {search_term_group_id};
                            """.format(search_term_group_id = format_range(search_term_group_id))

        if sql_query:
            sites_ids = [x.id for x in Sites.objects.raw(sql_query)]
            return Sites.objects.filter(id__in=sites_ids)

        return Sites.objects.all()


class BrandsViewSet(viewsets.ModelViewSet):
    serializer_class = BrandsSerializer
    http_method_names = ['get']

    filter_backends = (filters.DjangoFilterBackend,)
    filter_fields = ('id', 'name', 'image_url')

    def get_queryset(self):
        request = self.request
        product_list_id = request.query_params.get('product_list_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        site_id = request.query_params.get('site_id', None)

        # Check if more than 1 param from the this have been set
        if len(filter(None, [product_list_id, search_term_id])) > 1:
            raise ParamsCombinationError()

        sql_query = None

        if product_list_id and site_id:
            sql_query = """
                    select distinct rb.* from ranking_brands rb
                    join product_list_results_summary plrs on plrs.brand_id = rb.id
                    where plrs.product_list_id {product_list_id} and plrs.site_id {site_id};
                    """.format(product_list_id = format_range(product_list_id),
                               site_id = format_range(site_id))

        elif search_term_id and site_id:
            sql_query = """
                    select distinct rb.* from ranking_brands rb
                    join search_terms_brands_relation stbr on stbr.brand_id = rb.id
                    join ranking_search_results_items_summary rsris on rsris.search_items_brands_relation_id = stbr.id
                    where stbr.search_term_id {search_term_id} and rsris.site_id {site_id};
                    """.format(search_term_id = format_range(search_term_id),
                               site_id = format_range(site_id))

        if sql_query:
            brand_ids = [x.id for x in Brands.objects.raw(sql_query)]
            return Brands.objects.filter(id__in=brand_ids)

        return Brands.objects.all()


class DateViewSet(viewsets.ModelViewSet):
    serializer_class = DatesSerializer
    http_method_names = ['get']

    def get_queryset(self):
        request = self.request
        product_list_id = request.query_params.get('product_list_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        search_term_group_id = request.query_params.get('search_term_group_id', None)
        brand_id = request.query_params.get('brand_id', None)
        site_id = request.query_params.get('site_id', None)
        last_time = 'last_time' in request.query_params

        sql_query = None

        # Check if more than 1 param from the this have been set
        if len(filter(None, [product_list_id, search_term_id, search_term_group_id])) > 1:
            raise ParamsCombinationError()

        if product_list_id:
            if last_time:
                sql_query = """
                            select max(plrs.date) as date from product_list_results_summary plrs
                            where plrs.product_list_id {product_list_id};
                            """.format(product_list_id = format_range(product_list_id))

            elif brand_id and site_id:
                sql_query = """
                        select plrs.date as date from product_list_results_summary plrs
                        where product_list_id {product_list_id} and
                        plrs.site_id {site_id} and plrs.brand_id {brand_id};
                        """.format(product_list_id = format_range(product_list_id),
                                   brand_id = format_range(brand_id),
                                   site_id = format_range(site_id))

            else:
                sql_query = """
                            select distinct plrs.date as date from product_list_results_summary plrs
                            where plrs.product_list_id {product_list_id} order by date desc;
                            """.format(product_list_id = format_range(product_list_id))

        if search_term_group_id:
            if last_time:
                sql_query = """
                            select max(rsris.date_of_upload) as date from ranking_search_results_items_summary rsris
                            join search_terms_brands_relation stbr on stbr.id = rsris.search_items_brands_relation_id
                            join search_terms st on st.id = stbr.search_term_id
                            where st.group_id {search_term_group_id};
                            """.format(search_term_group_id = format_range(search_term_group_id))
            else:
                sql_query = """
                            select distinct rsris.date_of_upload as date from ranking_search_results_items_summary rsris
                            join search_terms_brands_relation stbr on stbr.id = rsris.search_items_brands_relation_id
                            join search_terms st on st.id = stbr.search_term_id
                            where st.group_id {search_term_group_id} order by date desc;
                            """.format(search_term_group_id = format_range(search_term_group_id))

        elif search_term_id and brand_id and site_id:
            sql_query = """
                    select rsris.date_of_upload as date from ranking_search_results_items_summary rsris
                    join search_terms_brands_relation stbr on stbr.brand_id = rsris.search_items_brands_relation_id
                    where stbr.search_term_id {search_term_id} and rsris.site_id {site_id} and stbr.brand_id {brand_id};
                    """.format(search_term_id = format_range(search_term_id),
                               brand_id = format_range(brand_id),
                               site_id = format_range(site_id))

        if sql_query:
            cursor = connection.cursor()
            cursor.execute(sql_query)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


class PriceDataViewSet(viewsets.ModelViewSet):
    serializer_class = PriceDataSerializer
    http_method_names = ['get']

    def get_queryset(self):
        request = self.request
        search_term_group_id = request.query_params.get('search_term_group_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        product_list_id = request.query_params.get('product_list_id', None)
        date = request.query_params.get('date', None)

        if not date:
            raise MissingParamError(
                'You need to included the param date with format YYYY-MM-DD')

        elif not any([search_term_group_id, search_term_id, product_list_id]):
            raise MissingParamError(
                'You need to included one of the following params:'
                ' search_term_group_id, search_term_id or product_list_id')

        date = checkAndFormatDates(date)

        sql_query = None

        if search_term_group_id:
            sql_query = """
                        select distinct on(rsri.url_id) st.title as search_term, pu.url as url, pu.title as title, rsri.price as price, rsri.currency as currency
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr on stbr.id = rsri.search_items_brands_relation_id
                        join search_terms st on st.id = stbr.search_term_id
                        join product_url pu on pu.id = rsri.url_id
                        where st.group_id {search_term_group_id} and rsri.date_of_upload {date};
                        """.format(search_term_group_id = format_range(search_term_group_id),
                            date=date)

        if search_term_id:
            sql_query = """
                        select distinct on(rsri.url_id) pu.url as url, pu.title as title, rsri.price as price, rsri.currency as currency
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr on stbr.id = rsri.search_items_brands_relation_id
                        join product_url pu on pu.id = rsri.url_id
                        where stbr.search_term_id {search_term_id} and rsri.date_of_upload {date};
                        """.format(search_term_id = format_range(search_term_id),
                            date=date)

        if product_list_id:
            sql_query = """
                        select distinct on(rsri.url_id) pu.url as url, pu.title as title, rsri.price as price, rsri.currency as currency
                        from ranking_search_results_items rsri
                        join product_url pu on pu.id = rsri.url_id
                        join product_list_items pli on pli.product_url_id = rsri.url_id
                        where pli.product_list_id {product_list_id} and rsri.date_of_upload {date};
                        """.format(product_list_id = format_range(product_list_id),
                            date=date)

        cursor = connection.cursor()
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class RankingDataViewSet(viewsets.ModelViewSet):
    serializer_class = RankingDataSerializer
    http_method_names = ['get']

    def get_queryset(self):
        request = self.request
        search_term_group_id = request.query_params.get('search_term_group_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        date = request.query_params.get('date', None)

        if not date:
            raise MissingParamError(
                'You need to included the param date with format YYYY-MM-DD')

        elif not any([search_term_group_id, search_term_id]):
            raise MissingParamError(
                'You need to included one of the following params:'
                ' search_term_group_id, search_term_id')

        date = checkAndFormatDates(date)

        sql_query = None

        if search_term_group_id:
            sql_query = """
                        select distinct on(rsri.url_id) st.title as search_term
                        , rsri.site_id as site_id, pu.url as url,
                         pu.title as title, rsri.ranking  as ranking
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join search_terms st on st.id = stbr.search_term_id
                        join product_url pu on pu.id = rsri.url_id
                        where st.group_id {search_term_group_id}
                            and rsri.date_of_upload {date};
                        """.format(search_term_group_id = format_range(search_term_group_id),
                            date=date)

        if search_term_id:
            sql_query = """
                        select distinct on(rsri.url_id) rsri.site_id, pu.url
                        , pu.title, rsri.ranking
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join product_url pu on pu.id = rsri.url_id
                        where stbr.search_term_id {search_term_id}
                            and rsri.date_of_upload {date};
                        """.format(search_term_id = format_range(search_term_id),
                            date=date)

        cursor = connection.cursor()
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class OutOfStockDataViewSet(viewsets.ModelViewSet):
    serializer_class = OutOfStockDataSerializer
    http_method_names = ['get']

    def get_queryset(self):
        request = self.request
        search_term_group_id = request.query_params.get('search_term_group_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        product_list_id = request.query_params.get('product_list_id', None)
        date = request.query_params.get('date', None)

        if not date:
            raise MissingParamError(
                'You need to included the param date with format YYYY-MM-DD')

        elif not any([search_term_group_id, search_term_id, product_list_id]):
            raise MissingParamError(
                'You need to included one of the following params:'
                ' search_term_group_id, search_term_id or product_list_id')

        date = checkAndFormatDates(date)

        sql_query = None

        if search_term_group_id:
            sql_query = """
                        select distinct on(rsri.url_id) st.title as search_term
                            , rsri.site_id as site_id, pu.url as url,
                            pu.title as title, rsri.is_out_of_stock
                            as is_out_of_stock, rsri.no_longer_available
                            as no_longer_available
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join search_terms st on st.id = stbr.search_term_id
                        join product_url pu on pu.id = rsri.url_id
                        where st.group_id {search_term_group_id}
                            and rsri.date_of_upload {date};
                        """.format(search_term_group_id = format_range(search_term_group_id),
                                   date=date)
        if search_term_id:
            sql_query = """
                        select distinct on(rsri.url_id) rsri.site_id
                            as site_id, pu.url as url,
                            pu.title as title, rsri.is_out_of_stock
                            as is_out_of_stock, rsri.no_longer_available
                            as no_longer_available
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join product_url pu on pu.id = rsri.url_id
                        where stbr.search_term_id {search_term_id}
                            and rsri.date_of_upload {date};
                        """.format(search_term_id = format_range(search_term_id),
                            date=date)

        if product_list_id:
            sql_query = """
                        select distinct on(rsri.url_id) pu.url as url,
                            pu.title as title, rsri.is_out_of_stock
                            as is_out_of_stock, rsri.no_longer_available
                            as no_longer_available
                        from ranking_search_results_items rsri
                        join product_url pu on pu.id = rsri.url_id
                        join product_list_items pli
                             on pli.product_url_id = rsri.url_id
                        where pli.product_list_id {product_list_id}
                             and rsri.date_of_upload {date};
                        """.format(product_list_id = format_range(product_list_id),
                            date=date)

        cursor = connection.cursor()
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class BuyBoxDataViewSet(viewsets.ModelViewSet):
    serializer_class = BuyBoxDataSerializer
    http_method_names = ['get']

    def get_queryset(self):
        request = self.request
        search_term_group_id = request.query_params.get('search_term_group_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        product_list_id = request.query_params.get('product_list_id', None)
        date = request.query_params.get('date', None)

        if not date:
            raise MissingParamError(
                'You need to included the param date with format YYYY-MM-DD')

        elif not any([search_term_group_id, search_term_id, product_list_id]):
            raise MissingParamError(
                'You need to included one of the following params:'
                ' search_term_group_id, search_term_id or product_list_id')

        date = checkAndFormatDates(date)

        sql_query = None

        if search_term_group_id:
            sql_query = """
                        select distinct on(rsri.url_id) st.title as
                            search_term, rsri.site_id as site_id, pu.url as url
                            , pu.title as title, m.name as marketplace,
                            rsri.is_out_of_stock as is_out_of_stock,
                            rsri.no_longer_available as no_longer_available,
                            pm.first_party_owned as first_party_owned
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join search_terms st on st.id = stbr.search_term_id
                        join product_url pu on pu.id = rsri.url_id
                        left join product_marketplace as pm
                            on pm.rsri_id = rsri.id
                        left join marketplace m on m.id = pm.marketplace_id
                        where st.group_id {search_term_group_id}
                                        and rsri.date_of_upload {date};
                        """.format(search_term_group_id = format_range(search_term_group_id),
                                   date=date)
        if search_term_id:
            sql_query = """
                        select distinct on(rsri.url_id) rsri.site_id
                            as site_id, pu.url as url
                            , pu.title as title, m.name as marketplace,
                            rsri.is_out_of_stock as is_out_of_stock,
                            rsri.no_longer_available as no_longer_available,
                            pm.first_party_owned as first_party_owned
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join product_url pu on pu.id = rsri.url_id
                        left join product_marketplace as pm
                            on pm.rsri_id = rsri.id
                        left join marketplace m on m.id = pm.marketplace_id
                        where stbr.search_term_id {search_term_id}
                                        and rsri.date_of_upload {date};
                        """.format(search_term_id = format_range(search_term_id),
                            date=date)

        if product_list_id:
            sql_query = """
                        select distinct on(rsri.url_id) pu.url as url
                            , pu.title as title, m.name as marketplace,
                            rsri.is_out_of_stock as is_out_of_stock,
                            rsri.no_longer_available as no_longer_available,
                            pm.first_party_owned as first_party_owned
                        from ranking_search_results_items rsri
                        join product_url pu on pu.id = rsri.url_id
                        join product_list_items pli
                            on pli.product_url_id = rsri.url_id
                        left join product_marketplace as pm
                            on pm.rsri_id = rsri.id
                        left join marketplace m on m.id = pm.marketplace_id
                        where pli.product_list_id {product_list_id}
                             and rsri.date_of_upload {date};
                        """.format(product_list_id = format_range(product_list_id),
                            date=date)

        cursor = connection.cursor()
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


class ReviewDataViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewDataSerializer
    http_method_names = ['get']

    def get_queryset(self):
        request = self.request
        search_term_group_id = request.query_params.get('search_term_group_id', None)
        search_term_id = request.query_params.get('search_term_id', None)
        product_list_id = request.query_params.get('product_list_id', None)
        date = request.query_params.get('date', None)

        if not date:
            raise MissingParamError(
                'You need to included the param date with format YYYY-MM-DD')

        elif not any([search_term_group_id, search_term_id, product_list_id]):
            raise MissingParamError(
                'You need to included one of the following params:'
                ' search_term_group_id, search_term_id or product_list_id')

        date = checkAndFormatDates(date)

        sql_query = None

        if search_term_group_id:
            sql_query = """
                        select distinct on(rsri.url_id) st.title as search_term
                            , rsri.site_id as site_id, pu.url as url
                            , pu.title as title, rbri.average_num
                            as average_num, rbri.total_count as total_count,
                            rbri.five_star as five_star, rbri.four_star
                            as four_star, rbri.three_star as three_star,
                            rbri.two_star as two_star,
                            rbri.one_star as one_star
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join search_terms st on st.id = stbr.search_term_id
                        join product_url pu on pu.id = rsri.url_id
                        left join ranking_buyers_review_info as rbri
                            on rbri.rsri_id = rsri.id
                        where st.group_id {search_term_group_id}
                                        and rsri.date_of_upload {date};
                        """.format(search_term_group_id = format_range(search_term_group_id),
                                   date=date)
        if search_term_id:
            sql_query = """
                        select distinct on(rsri.url_id) rsri.site_id as site_id
                            , pu.url as url, pu.title as title,
                            rbri.average_num as average_num, rbri.total_count
                            as total_count, rbri.five_star as five_star,
                            rbri.four_star as four_star, rbri.three_star
                            as three_star, rbri.two_star as two_star,
                            rbri.one_star as one_star
                        from ranking_search_results_items rsri
                        join search_terms_brands_relation stbr
                            on stbr.id = rsri.search_items_brands_relation_id
                        join product_url pu on pu.id = rsri.url_id
                        left join ranking_buyers_review_info as rbri
                            on rbri.rsri_id = rsri.id
                        where stbr.search_term_id {search_term_id}
                                        and rsri.date_of_upload {date};
                        """.format(search_term_id = format_range(search_term_id),
                            date=date)

        if product_list_id:
            sql_query = """
                        select distinct on(rsri.url_id) pu.url as url,
                            pu.title as title,
                            rbri.average_num as average_num, rbri.total_count
                            as total_count, rbri.five_star as five_star,
                            rbri.four_star as four_star, rbri.three_star
                            as three_star, rbri.two_star as two_star,
                            rbri.one_star as one_star
                        from ranking_search_results_items rsri
                        join product_url pu on pu.id = rsri.url_id
                        join product_list_items pli
                            on pli.product_url_id = rsri.url_id
                        left join ranking_buyers_review_info as rbri
                            on rbri.rsri_id = rsri.id
                        where pli.product_list_id {product_list_id}
                             and rsri.date_of_upload {date};
                        """.format(product_list_id = format_range(product_list_id),
                            date=date)

        cursor = connection.cursor()
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
