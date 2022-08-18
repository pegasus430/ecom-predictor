import csv
from datetime import date
import re
import requests
import urlparse
import traceback

from . import SitemapSpider, SitemapSpiderError
from app.models import db, Semrush


class SamsClubSitemapSpider(SitemapSpider):
    retailer = 'samsclub.com'

    SITEMAP_URL = 'https://www.samsclub.com/sitemap.xml'
    STORES_URL = 'https://www.samsclub.com/sitemap_locators.xml'

    SHELF_API_URL = 'https://www.samsclub.com/soa/services/v1/catalogsearch/search'
    API_HEADERS = {
        'WM_SVC.VERSION': '1.0.0',
        'WM_SVC.ENV': 'prod',
        'WM_SVC.NAME': 'sams-api',
        'WM_QOS.CORRELATION_ID': '123456abcdef',
        'WM_CONSUMER.ID': '6a9fa980-1ad4-4ce0-89f0-79490bbc7625'
    }

    SEMRUSH_KEY = 'e333e9506cd32ad922850a653179898e'

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        products_seen = set()

        with open(self.get_file_path_for_result('samsclub_products.csv'), 'wb') as urls_file:
            urls_csv = csv.writer(urls_file)

            for url in self._parse_sitemap(self.SITEMAP_URL):
                product_id = re.search(r'samsclub\.com/sams/(?:.*/)?(?:prod)?(\d+)\.ip', url)

                if product_id:
                    product_id = int(product_id.group(1))

                    if product_id not in products_seen:
                        products_seen.add(product_id)

                        urls_csv.writerow([url])

        urls_file.close()

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])

        failed_urls = []
        for shelf_url in shelf_urls:
            try:
                shelf_url_parts = urlparse.urlparse(shelf_url)

                category_id = re.search(r'/(\d+)\.cp', shelf_url_parts.path)
                if not category_id:
                    self.logger.warn('Invalid shelf url: {}'.format(shelf_url))
                    continue

                category_id = category_id.group(1)

                # initial params
                params = {
                    'limit': 48,
                    'navigate': 1,
                    'offset': 0,
                    'pageView': 'grid',
                    'recordType': 'all',
                    'searchCategoryId': category_id,
                    'totalLimit': 48
                }

                # add params from shelf url
                shelf_url_params = urlparse.parse_qs(shelf_url_parts.query)

                if shelf_url_params:
                    params.update(shelf_url_params)
                    item_urls_filename = '{}_{}.csv'.format(
                        category_id,
                        self._url_to_filename(shelf_url_parts.query)
                        if isinstance(shelf_urls, list) else shelf_urls[shelf_url])
                else:
                    item_urls_filename = '{}.csv'.format(
                        category_id if isinstance(shelf_urls, list) else shelf_urls[shelf_url])

                with open(self.get_file_path_for_result(item_urls_filename), 'w') as item_urls_file:
                    item_urls_writer = csv.writer(item_urls_file)

                    while True:
                        self.logger.info('Scraping shelf page with params: {}'.format(params))

                        response = requests.get(self.SHELF_API_URL, params=params, headers=self.API_HEADERS)

                        self._check_response(response, raise_error=True)

                        data = response.json()

                        status = data.get('status')
                        if status != 'OK':
                            raise SitemapSpiderError('Wrong response status: {}'.format(status))

                        payload = data.get('payload', {})

                        item_urls = [record.get('seoUrl') for record in payload.get('records', [])]
                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_urls_writer.writerow([urlparse.urljoin(response.url, item_url)])

                        if params['offset'] + params['limit'] < payload.get('totalRecords'):
                            params['offset'] += params['limit']
                            params['navigate'] += 1
                        else:
                            break
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def task_geo_report(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        report_name = options.get('request_name') or 'geo_report'

        with open(self.get_file_path_for_result('{}.csv'.format(report_name)), 'wb') as geo_report_file:
            csv_writer = csv.writer(geo_report_file)
            csv_writer.writerow(['URL', 'Store ID', 'Pick up in Club available'])

            stores = options.get('stores') or self._get_stores()

            failed_urls = []
            for store in stores:
                zip_code = None
                store_id = None

                if isinstance(store, dict):
                    zip_code = store.get('zip_code')
                    store_id = store.get('store_id')
                elif isinstance(store, (list, tuple)):
                    if len(store) == 1:
                        store_id = store[0],
                    elif len(store) > 1:
                        zip_code = store[0],
                        store_id = store[1]
                else:
                    store_id = store

                if zip_code and not store_id:
                    store_id = self._get_store_id(zip_code)

                if not store_id:
                    self.logger.warn('Missing store id for zip_code: {}'.format(zip_code))
                    continue

                self.logger.info('Loading info for store id: {}'.format(store_id))

                for url in options.get('urls', []):
                    try:
                        product_info = self._get_product_info(url, store_id)

                        csv_writer.writerow([url, store_id, product_info.get('pickup')])
                    except:
                        self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                        if url not in failed_urls:
                            failed_urls.append(url)
            if failed_urls:
                self.save_failed_urls(failed_urls)
                raise SitemapSpiderError('Some urls cannot be processed')

    def _get_stores(self):
        stores = []

        for store_url in self._parse_sitemap(self.STORES_URL, follow=False):
            store_id = re.search(r'/(\d+)$', store_url)

            if store_id:
                stores.append({'store_id': store_id.group(1)})

        return stores

    def _get_store_id(self, zip_code):
        self.logger.info('Search store for zip code: {}'.format(zip_code))

        store_search_url = 'https://www.samsclub.com/api/node/clubfinder/list?' \
                           'distance=100&nbrOfStores=20&singleLineAddr={zip_code}'.format(zip_code=zip_code)

        response = requests.get(store_search_url, timeout=60)

        if self._check_response(response):
            stores = response.json()

            if stores:
                return stores[0].get('id')

    def _get_product_info(self, url, store_id):
        self.logger.debug('Checking store {}: {}'.format(store_id, url))

        product_info = {
            'pickup': False,
        }

        for i in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.API_HEADERS, cookies={'myPreferredClub': str(store_id)},
                                        timeout=60)

                if self._check_response(response):
                    if 'addtocartsingleajaxclub' in response.content:
                        product_info['pickup'] = True
            except:
                self.logger.error('Product info error: {}'.format(traceback.format_exc()))
            else:
                break

        return product_info

    def task_semrush(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        ignore_cache = options.get('ignore_cache')
        product_urls = options.get('urls', [])

        failed_urls = []
        for product_url in product_urls:
            try:
                self.logger.info('Processing URL: {}'.format(product_url))

                self._semrush_url_organic(product_url, ignore_cache=ignore_cache)
                self._semrush_backlinks_overview(product_url, ignore_cache=ignore_cache)
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                db.session.rollback()
                failed_urls.append(product_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def _get_seo_url(self, url):
        self.logger.info('Getting SEO url for {}'.format(url))

        product_id = re.search(r'samsclub\.com/sams/(?:.*/)?((?:prod)?\d+)\.ip', url)

        if product_id:
            redirect_url = 'https://www.samsclub.com/sams/shop/product.jsp?productId={}'.format(product_id.group(1))

            for i in range(self.max_retries):
                try:
                    response = requests.get(redirect_url, headers=self.API_HEADERS, timeout=60, allow_redirects=False)
                except:
                    self.logger.error('Getting SEO url error: {}'.format(traceback.format_exc()))
                else:
                    seo_url = response.headers.get('location')

                    if seo_url:
                        return seo_url.split('?')[0]

                    break

        return url

    def _semrush_url_organic(self, url, try_other_url=True, ignore_cache=False):
        today = date.today()

        cache = Semrush.query.filter_by(url=url).first()
        if not ignore_cache and cache and cache.url_organic_date == today:
            self.logger.info('Using cached Semrush url_organic report for {}'.format(url))
        else:
            self.logger.info('Loading Semrush url_organic report for {}'.format(url))
            if not cache:
                cache = Semrush(url=url)
                db.session.add(cache)

            endpoint = 'https://api.semrush.com/'

            params = {
                'type': 'url_organic',
                'key': self.SEMRUSH_KEY,
                'url': url,
                'database': 'us',
                'display_limit': 200,
                'export_columns': 'Ph,Po,Nq,Cp,Co,Tr,Tc'
            }

            try:
                response = requests.get(endpoint, params=params)
                response.raise_for_status()
            except:
                self.logger.error('Can not load Semrush report: {}'.format(traceback.format_exc()))
                return
            else:
                cache.url_organic = response.text
                cache.url_organic_date = today

        if 'ERROR 50' in cache.url_organic and try_other_url:
            if cache.seo_url:
                self.logger.info('Using cached SEO url for {}'.format(url))
            else:
                cache.seo_url = self._get_seo_url(url)

            if cache.seo_url != url:
                db.session.commit()

                self.logger.info('Processing SEO URL: {}'.format(cache.seo_url))
                self._semrush_url_organic(cache.seo_url, False, ignore_cache)

                return

        db.session.commit()

        product_id = re.search(r'(\d+)\.ip', url)
        if product_id:
            report_filename = product_id.group(1)
        else:
            report_filename = self._url_to_filename(url)

        report_filepath = self.get_file_path_for_result('{}_url_organic.csv'.format(report_filename))

        with open(report_filepath, 'w') as report_file:
            report_file.write(cache.url_organic.encode('utf-8'))

    def _semrush_backlinks_overview(self, url, try_other_url=True, ignore_cache=False):
        today = date.today()

        cache = Semrush.query.filter_by(url=url).first()
        if not ignore_cache and cache and cache.backlinks_overview_date == today:
            self.logger.info('Using cached Semrush backlinks_overview report for {}'.format(url))
        else:
            self.logger.info('Loading Semrush backlinks_overview report for {}'.format(url))
            if not cache:
                cache = Semrush(url=url)
                db.session.add(cache)

            endpoint = 'https://api.semrush.com/analytics/v1/'

            params = {
                'type': 'backlinks_overview',
                'key': self.SEMRUSH_KEY,
                'target': url,
                'target_type': 'url',
                'export_columns': 'total'
            }

            try:
                response = requests.get(endpoint, params=params)
                response.raise_for_status()
            except:
                self.logger.error('Can not load Semrush report: {}'.format(traceback.format_exc()))
                return
            else:
                cache.backlinks_overview = response.text
                cache.backlinks_overview_date = today

        if 'ERROR 50' in cache.backlinks_overview and try_other_url:
            if cache.seo_url:
                self.logger.info('Using cached SEO url for {}'.format(url))
            else:
                cache.seo_url = self._get_seo_url(url)

            if cache.seo_url != url:
                db.session.commit()

                self.logger.info('Processing SEO URL: {}'.format(cache.seo_url))
                self._semrush_backlinks_overview(cache.seo_url, False, ignore_cache)

                return

        db.session.commit()

        product_id = re.search(r'(\d+)\.ip', url)
        if product_id:
            report_filename = product_id.group(1)
        else:
            report_filename = self._url_to_filename(url)

        report_filepath = self.get_file_path_for_result('{}_backlinks_overview.csv'.format(report_filename))

        with open(report_filepath, 'w') as report_file:
            report_file.write(cache.backlinks_overview.encode('utf-8'))
