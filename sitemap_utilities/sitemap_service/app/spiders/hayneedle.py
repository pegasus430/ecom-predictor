import csv
import re
import traceback
import urllib
import urlparse
import uuid

import requests

from . import SitemapSpider, SitemapSpiderError


class HayneedleSitemapSpider(SitemapSpider):
    retailer = 'hayneedle.com'

    SITEMAP_URL = 'https://www.hayneedle.com/sitemapIndex.xml'

    shelf_url_template = "https://www.hayneedle.com/shared/templates/ajax/angular/result_list.cfm?categoryId={categoryid}&selectedFacets={selectedfacets}&page={page}&sortBy=preferred:desc&checkCache=true&qs=&fm=&pageType=PRODUCT_CATEGORY&view=48&action=filter_category_results&instart_disable_injection=true"

    required_params = ['categoryid', 'selectedfacets']

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        for sitemap_product_url in self._parse_sitemap(self.SITEMAP_URL, follow=False, headers=self._get_antiban_headers(),
                                               proxies=self._get_proxies()):
            category = re.search(r'sitemap_product_(.*?)-\d+\.xml', sitemap_product_url)

            if category:
                category_name = category.group(1)

                with open(self.get_file_path_for_result('{}.csv'.format(category_name)), 'a') as urls_file:
                    urls_csv = csv.writer(urls_file)

                    for url in self._parse_sitemap(sitemap_product_url, headers=self._get_antiban_headers(),
                                                   proxies=self._get_proxies()):
                        if 'hayneedle.com/product/' in url:
                            urls_csv.writerow([url])

    def _get_antiban_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:32.0) Gecko/20100101 Firefox/32.0',
            'Connection': 'keep-alive',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate'
        }

    def _get_proxies(self):
        return {
            'http': 'http://proxy_out.contentanalyticsinc.com:8231',
            'https': 'http://proxy_out.contentanalyticsinc.com:8231',
        }

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])

        failed_urls = []
        for shelf_url in shelf_urls:
            try:
                item_urls_filename = '{}.csv'.format(
                    self._url_to_filename(shelf_url if isinstance(shelf_urls, list) else shelf_urls[shelf_url]))

                with open(self.get_file_path_for_result(item_urls_filename), 'w') as item_urls_file:
                    item_urls_writer = csv.writer(item_urls_file)

                    format_parameters = {'page': 1}
                    format_parameters.update(self._parse_required_url_parameters(shelf_url, self.required_params))

                    shelf_url = self.shelf_url_template.format(**format_parameters)

                    while True:
                        self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                        for _ in range(3):
                            response = requests.get(shelf_url, headers=self._get_antiban_headers(),
                                                    proxies=self._get_proxies(), timeout=60)

                            self._check_response(response, raise_error=True)

                            try:
                                data = response.json()
                                break
                            except:
                                self.logger.warn('Response is not JSON. Retry request')
                        else:
                            raise SitemapSpiderError('Spider was banned')

                        item_urls = []

                        for item in data.get('filteredResults', []):
                            item_url = item.get('url')

                            if item_url:
                                item_urls.append(item_url)

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()

                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_urls_writer.writerow([urlparse.urljoin(response.url, item_url)])

                        next_page = data.get('pagenation', {}).get('nextPage')

                        if next_page:
                            format_parameters['page'] = next_page
                            shelf_url = self.shelf_url_template.format(**format_parameters)
                        else:
                            break
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def _parse_required_url_parameters(self, url, required_parameters_keys):
        url_parts = urlparse.urlparse(url.lower())

        parameters = urlparse.parse_qs(url_parts.fragment or url_parts.query)

        if all(param in parameters for param in required_parameters_keys):
            return {param: urllib.quote_plus(parameters.get(param)[0]).upper()
                    for param in required_parameters_keys}
        else:
            parameters = {param: '' for param in required_parameters_keys}

            ids = re.findall(r'_(\d+)', url_parts.path)

            if ids:
                parameters['categoryid'] = ids[0]

                if len(ids) > 1:
                    # parse available facets
                    facets_id = ids[1:]

                    facets_url = self.shelf_url_template.format(page=1, **parameters)

                    for _ in range(3):
                        response = requests.get(facets_url, headers=self._get_antiban_headers(),
                                                proxies=self._get_proxies(), timeout=60)

                        self._check_response(response, raise_error=True)

                        try:
                            data = response.json()
                            break
                        except:
                            self.logger.warn('Response is not JSON. Retry request')
                    else:
                        raise SitemapSpiderError('Spider was banned')

                    facets = {}

                    for facet_id in facets_id:
                        for facet in data.get('facets', []):
                            if int(facet_id) in (x.get('id') for x in facet.get('values', [])):
                                facets.setdefault('{:.0f}'.format(facet.get('id')), []).append(facet_id)

                    facets = [(key, '~'.join(value)) for key, value in facets.iteritems()]
                    facets = [key + '|' + value for key, value in facets]

                    parameters['selectedfacets'] = '^'.join(facets)
            else:
                raise SitemapSpiderError('Can not parse category from url: {}'.format(url))

            return parameters
