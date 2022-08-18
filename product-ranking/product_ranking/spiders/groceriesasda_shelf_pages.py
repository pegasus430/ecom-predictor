# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
import traceback
import json

from product_ranking.spiders.groceriesasda import GroceriesAsdaProductsSpider
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from scrapy.http import Request

from spiders_shared_code.utils import deep_search


class GroceriesAsdaShelfPagesSpider(GroceriesAsdaProductsSpider):
    name = 'groceriesasda_shelf_urls_products'
    allowed_domains = ["groceries.asda.com"]

    prods_per_page = 60

    CATEGORY_URL = "https://groceries.asda.com/api/items/viewitemlist?catid={catid}&deptid={deptid}" \
                   "&aisleid={aisleid}&showfacets=1&pagesize={prods_per_page}&pagenum={pagenum}" \
                   "&contentids=New_IM_ShelfPage_FirstRow_1%2CNew_IM_ShelfPage_LastRow_1%2CNew_IM_SEO_ListingPage_Bottom_promo" \
                   "%2CNew_IM_Second_Navi_Shelf&storeid=4565&cacheable=true&shipDate=currentDate" \
                   "&sortby=relevance+desc&facets=shelf%3A0000%3A{catid}&requestorigin=gi"

    CATEGORIES_URL = "https://groceries.asda.com/api/categories/viewmenu?" \
                     "cacheable=true&storeid=4565&requestorigin=gi"

    use_proxies = False

    HEADERS = {
        'Accept-Language': 'en-US,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) ' \
                      'AppleWebKit/537.36 (KHTML, like Gecko)' \
                      'Chrome/55.0.2883.95 Safari/537.36',
        'x-forwarded-for': '127.0.0.1'
    }

    ADS_DEPT_URL = 'https://groceries.asda.com/cmscontent/json/pages/browse/{level}?Endeca_user_segments=anonymous' \
                   '%7Cstore_4565%7Cwapp%7Cvp_M%7CZero_Order_Customers%7Cdp-false%7C1007%7C1019%7C1020%7C1023' \
                   '%7C1024%7C1027%7C1038%7C1041%7C1042%7C1043%7C1047%7C1053%7C1055%7C1057%7C1059%7C1067%7C1070' \
                   '%7C1082%7C1087%7C1097%7C1098%7C1099%7C1100%7C1102%7C1105%7C1107%7C1109%7C1110%7C1111%7C1112' \
                   '%7C1116%7C1117&storeId=4565&shipDate=1513670400000&N={level_id}&No=0&Nrpp=60&requestorigin=gi'

    ADS_MINI_URL = 'https://groceries.asda.com/cmscontent/json/pages/browse/mini-trolley?Endeca_user_segments=anonymous' \
                   '%7Cstore_4565%7Cwapp%7Cvp_XL%7CZero_Order_Customers%7Cdp-false%7C1007%7C1019%7C1020%7C1023%7C1024' \
                   '%7C1027%7C1038%7C1041%7C1042%7C1043%7C1047%7C1053%7C1055%7C1057%7C1059%7C1067%7C1070%7C1082%7C1087' \
                   '%7C1097%7C1098%7C1099%7C1100%7C1102%7C1105%7C1107%7C1109%7C1110%7C1111%7C1112%7C1116%7C1117' \
                   '&storeId=4565&shipDate=1513670400000&No=0&Nrpp=60&requestorigin=gi'

    ADS_OFFERS_URL = 'https://groceries.asda.com/cmscontent/json/pages/special-offers/all-offers/{level}' \
                     '?Endeca_user_segments=anonymous%7Cstore_4565%7Cwapp%7Cvp_M%7CZero_Order_Customers' \
                     '%7Cdp-false%7C1007%7C1019%7C1020%7C1023%7C1024%7C1027%7C1038%7C1041%7C1042%7C1043%7C1047' \
                     '%7C1053%7C1055%7C1057%7C1059%7C1067%7C1070%7C1082%7C1087%7C1097%7C1098%7C1099%7C1100' \
                     '%7C1102%7C1105%7C1107%7C1109%7C1110%7C1111%7C1112%7C1116%7C1117&storeId=4565' \
                     '&shipDate=1516780800000&N={level_id}&Nrpp=60&No=0&requestorigin=gi'

    ADS_SINGLE_ITEM_URL = 'https://groceries.asda.com/api/items/view?itemid={item_id}&responsegroup=extended' \
                       '&cacheable=true&storeid=4565&shipdate=currentDate&requestorigin=gi'

    ITEMS_URL = 'https://groceries.asda.com/cmscontent/json/pages/browse/shelf?Endeca_user_segments=anonymous' \
                '%7Cstore_4565%7Cwapp%7Cvp_S%7CZero_Order_Customers%7Cdp-false%7C1007%7C1019%7C1020%7C1023%7C1024' \
                '%7C1027%7C1038%7C1041%7C1042%7C1043%7C1047%7C1053%7C1055%7C1057%7C1059%7C1067%7C1070%7C1082%7C1087' \
                '%7C1097%7C1098%7C1099%7C1100%7C1102%7C1105%7C1107%7C1109%7C1110%7C1111%7C1112%7C1116%7C1117' \
                '&storeId=4565&shipDate=1515398400000&N={level_id}&No=0&Nrpp=60&requestorigin=gi&_=1515436884948'

    ITEMS_EVENT_URL = 'https://groceries.asda.com/cmscontent/json/pages/cmslisting/content/{level}' \
                      '?Endeca_user_segments=anonymous%7Cstore_4565%7Cwapp%7Cvp_XL%7CZero_Order_Customers' \
                      '%7CDelivery_Pass_Older_Than_12_Months%7Cdp-false%7C1007%7C1019%7C1020%7C1023%7C1024' \
                      '%7C1027%7C1038%7C1041%7C1042%7C1043%7C1047%7C1053%7C1055%7C1057%7C1059%7C1067%7C1070' \
                      '%7C1082%7C1087%7C1097%7C1098%7C1099%7C1100%7C1102%7C1105%7C1107%7C1109%7C1110%7C1111' \
                      '%7C1112%7C1116%7C1117%7C1119%7C1123%7C1124%7C1126%26storeId%3D4565%26shipDate' \
                      '%3D1522371600000%26N%3D{level_id}%26No%3D0%26Nrpp%3D60' \
                      '%26requestorigin%3Dgi%26_%3D1522417984349'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', 1))

        self.detect_ads_shelf = False
        detect_ads = kwargs.pop('detect_ads', False)

        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads_shelf = True

        self.search_term = ''

        self.categories = []
        self.category_id = 0
        self.department_id = 0
        self.aisle_id = 0
        self.checked_dept_ads = False

        super(GroceriesAsdaShelfPagesSpider, self).__init__(
            *args,
            **kwargs)

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        try:
            self.search_term = re.search('shelf/(.*)', self.product_url).group(1).split('/')[1]
        except Exception as e:
            self.log('Error while parsing search_term {}'.format(traceback.format_exc(e)))

        return {'remaining': self.quantity, 'search_term': self.search_term}.copy()

    def start_requests(self):
        if self.detect_ads_shelf:
            request = Request(
                self.ADS_MINI_URL,
                headers=self.HEADERS,
                callback=self._start_ads_request,
                meta=self._setup_meta_compatibility()
            )
        else:
            request = Request(
                self.CATEGORIES_URL,
                headers=self.HEADERS,
                callback=self._start_requests,
                meta=self._setup_meta_compatibility()
            )

        yield request

    def _start_requests(self, response):
        meta = response.meta.copy()
        try:
            data = json.loads(response.body_as_unicode())
            self.categories = data.get('categories')
        except Exception as e:
            self.log('Error while parsing categories {}'.format(traceback.format_exc(e)))

        category, dept, aisle, shelf = self._get_path()

        if dept and aisle:
            self.department_id = dept
            self.aisle_id = aisle
            self.category_id = shelf

            yield Request(
                self.CATEGORY_URL.format(
                    pagenum=self.current_page,
                    prods_per_page=self.prods_per_page,
                    search_term=self.search_term,
                    catid=self.category_id,
                    deptid=self.department_id,
                    aisleid=self.aisle_id
                ),
                meta=meta
            )
        elif self.detect_ads_shelf and meta.get('ads'):
            prod = SiteProductItem()
            prod['ads'] = meta.get('ads')

            yield prod

    def _get_prod(self, item):
        prod = SiteProductItem()

        prod['title'] = item.get('itemName')
        prod['brand'] = item.get('brandName')

        if item.get('price'):
            prod['price'] = Price(
                price=item.get('price').replace('£', '').replace(
                    ',', '').strip(),
                priceCurrency='GBP'
            )

        try:
            total_stars = int(item['totalReviewCount'])
            avg_stars = float(item['avgStarRating'])
            prod['buyer_reviews'] = BuyerReviews(num_of_reviews=total_stars,
                                                 average_rating=avg_stars,
                                                 rating_by_star={})
        except:
            self.log('Reviews Error {}'.format(traceback.format_exc()))

        prod['model'] = item.get('cin')
        image_url = item.get('imageURL')
        if not image_url and "images" in item:
            image_url = item.get('images', {}).get('largeImage')
        prod['image_url'] = image_url

        pId = item.get('id')
        name = item.get('name')
        shelf_name = item.get('shelfName')
        if pId and name and shelf_name:
            shelf_name, name = ["-".join(re.split('\W+', x)).lower() for x in [shelf_name, name]]
            prod['url'] = self.PRODUCT_LINK.format(shelfName=shelf_name, name=name, pId=pId)

        prod["image_url"] = item.get('imageURL')
        prod['locale'] = "en-GB"

        return prod

    def _scrape_product_links(self, response):
        items = []
        try:
            items = json.loads(response.body_as_unicode())['items']
        except:
            self.log('Product Links Error {}'.format(traceback.format_exc()))

        meta = response.meta.copy()

        for item in items:
            prod = self._get_prod(item)
            products_ids = item['id']
            url = self.API_URL.format(id=products_ids)

            if self.detect_ads_shelf:
                prod['ads'] = meta.get('ads')

            yield url, prod

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        try:
            data = json.loads(response.body_as_unicode())
            max_page = int(data['maxPages'])
            if self.current_page >= max_page:
                return

            self.current_page += 1

            return Request(
                self.CATEGORY_URL.format(
                    pagenum=self.current_page,
                    prods_per_page=self.prods_per_page,
                    search_term=self.search_term,
                    catid=self.category_id,
                    deptid=self.department_id,
                    aisleid=self.aisle_id
                ),
                meta=self._setup_meta_compatibility(),
                headers=self.HEADERS,
            )
        except Exception as e:
            self.log('Page Count Error {}'.format(traceback.format_exc(e)))

    def _get_path(self):
        try:
            wrap = re.findall('(?<=/)\d+', self.product_url)[0]

            for category in self.categories:
                depts = category.get('categories', [])
                for dept in depts:
                    aisles = dept.get('categories', [])
                    for aisle in aisles:
                        shelves = aisle.get('categories', [])
                        for shelf in shelves:

                            if wrap == shelf.get('dimensionid'):
                                return category.get('id'), dept.get('id'), aisle.get('id'), shelf.get('id')
        except Exception as e:
            self.log('Error while parsing categories {}'.format(traceback.format_exc(e)))

        return None, None, None, None

    def _get_ads(self, response):
        ads = []
        data = None
        contents = []

        try:
            data = json.loads(response.body_as_unicode())
        except Exception as e:
            self.log('Error while parsing search_term {}'.format(traceback.format_exc(e)))

        if deep_search('mainContent', data):
            contents.extend(deep_search('mainContent', data)[0])
        if deep_search('secondaryNav', data):
            contents.extend(deep_search('secondaryNav', data)[0])

        for content in contents:
            try:
                media_content = content.get('contents', [{}])[0]
                media_url = media_content.get('mediaURL')
                if not media_url:
                    media_content = media_content.get('dynamicSlot', {}).get('contents', [{}])[0]
                    media_url = media_content['mediaURL']

                path = media_content.get('link', {}).get('path')
                query = media_content.get('link', {}).get('queryString')
                if media_url and path:
                    ads.append({
                        'ad_image': media_url,
                        'ad_path': path,
                        'ad_query': query
                    })
            except:
                continue

        if deep_search('mediaItems', data):
            media_items = deep_search('mediaItems', data)[0]
            for media_item in media_items:
                media_url = media_item.get('mediaURL')
                path = media_item.get('link', {}).get('path')
                query = media_item.get('link', {}).get('queryString')
                if media_url and path and query:
                    ads.append({
                        'ad_image': media_url,
                        'ad_path': path,
                        'ad_query': query
                    })

        return ads

    def _get_level(self):
        level = None
        splits = self.product_url.split('/')
        if 'dept' in splits:
            level = 'dept'
        elif 'asile' in splits:
            level = 'asile'
        elif 'cat' in splits:
            level = 'cat'
        elif 'by-category' in splits:
            level = 'by-category'

        level_id = re.search(r'\d+', self.product_url)
        if level_id:
            level_id = level_id.group()

        return level, level_id

    def _get_item_url(self, shelf_name, name, item_id):
        shelf_name, name = ["-".join(re.split('\W+', x)).lower() for x in [shelf_name, name]]
        return self.PRODUCT_LINK.format(shelfName=shelf_name, name=name, pId=item_id)

    def _get_items(self, items_data):
        items = []
        item_groups = deep_search('records', items_data)
        if item_groups:
            item_groups = item_groups[0]

            for item_group in item_groups:
                item_group = item_group.get('attributes', {})
                item_name = item_group.get('sku.displayName')
                item_id = item_group.get('sku.repositoryId')
                item_shelf_name = item_group.get('sku.shelfName')

                if item_name and item_id and item_shelf_name:
                    items.append({
                        'name': item_name[0],
                        'reseller_id': item_id[0],
                        'url': self._get_item_url(item_shelf_name[0], item_name[0], item_id[0])
                    })

        else:
            # single item on page
            single_item = items_data.get('items')
            if single_item:
                items.append({
                    'name': single_item[0].get('name'),
                    'reseller_id': single_item[0].get('id'),
                    'url': single_item[0].get('productURL')
                })

        return items

    def _get_ads_products(self, response):
        meta = response.meta.copy()
        ads = meta.get('ads', [])
        reqs = meta.get('reqs', [])

        items_data = None
        try:
            items_data = json.loads(response.body)
        except Exception as e:
            self.log('Ads Product Error {}'.format(traceback.format_exc(e)))

        if items_data:
            items = self._get_items(items_data)

            ad_query = re.search(r'N=(\d+)', response.url)
            if not ad_query:
                ad_query = re.search(r'itemid=(\d+)', response.url)

            if ad_query:
                ad_query = ad_query.group(1)

            ad_idx = 0
            for idx, ad in enumerate(ads):
                if ad_query and ad_query in ad['ad_url']:
                    ad_idx = idx
                    break

            ads[ad_idx]['ad_dest_products'] = items
            response.meta['ads'] = ads

        if reqs:
            return self.send_next_request(reqs, response)

        return Request(
            self.CATEGORIES_URL,
            headers=self.HEADERS,
            callback=self._start_requests,
            meta=meta
        )

    def _start_ads_request(self, response):
        meta = response.meta.copy()

        ads = meta.get('ads', [])
        reqs = meta.get('reqs', [])

        ads_groups = self._get_ads(response)

        for ads_group in ads_groups:
            if ads_group.get('ad_query'):
                ad = {
                    'ad_url': urlparse.urljoin(response.url, ads_group['ad_path'].replace('/pages/ASDASearch', '')
                                               + '?' + ads_group.get('ad_query')),
                    'ad_image': ads_group['ad_image']
                }
            else:
                ad = {
                    'ad_url': urlparse.urljoin(response.url, ads_group['ad_path']),
                    'ad_image': ads_group['ad_image']
                }
            ads.append(ad)

        response.meta['ads'] = ads

        level, level_id = self._get_level()

        if self.checked_dept_ads is False and level and level_id:
            self.checked_dept_ads = True
            reqs.append(
                Request(
                    self.ADS_DEPT_URL.format(level=level, level_id=level_id),
                    headers=self.HEADERS,
                    callback=self._start_ads_request,
                    meta=meta
                )
            )

            if 'by-category' in self.product_url:
                reqs.append(
                    Request(
                        self.ADS_OFFERS_URL.format(level=level, level_id=level_id),
                        headers=self.HEADERS,
                        callback=self._start_ads_request,
                        meta=meta
                    )
                )
        elif ads:
            for ad in ads:
                ad_query = re.search(r'\d{3,}', ad['ad_url'])
                level = re.search(r'content/(.*)\?N', ad['ad_url'])
                if not ad_query:
                    break

                if level:
                    reqs.append(
                        Request(
                            url=self.ITEMS_EVENT_URL.format(level=level.group(1), level_id=ad_query.group().replace('+', '%2B')),
                            callback=self._get_ads_products,
                            headers=self.HEADERS,
                            dont_filter=True,
                            meta=meta
                        )
                    )
                else:
                    reqs.append(
                        Request(
                            url=self.ADS_SINGLE_ITEM_URL.format(item_id=ad_query.group()),
                            callback=self._get_ads_products,
                            headers=self.HEADERS,
                            dont_filter=True,
                            meta=meta
                        )
                    )

        if reqs:
            return self.send_next_request(reqs, response)

        return Request(
            self.CATEGORIES_URL,
            headers=self.HEADERS,
            callback=self._start_requests,
            meta=meta
        )

    def _parse_total_matches(self, response):
        return self._scrape_total_matches(response)

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)
