import csv
import requests
import json
import uuid
import urlparse
import traceback

from lxml import etree

from . import SitemapSpider, SitemapSpiderError


class OcadoSitemapSpider(SitemapSpider):
    retailer = 'ocado.com'

    item_url_template = 'https://www.ocado.com/webshop/product/ABC/{sku}'

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

                    while True:
                        self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                        response = requests.get(shelf_url, timeout=60)

                        self._check_response(response, raise_error=True)

                        tree = etree.HTML(response.content)

                        item_urls = []
                        skus = []

                        js_data = tree.xpath(".//script[@type='application/json' and @class='js-productPageJson']/text()")

                        if js_data:
                            try:
                                data = json.loads(js_data[0])

                                for section in data.get('sections', []):
                                    for fop in section.get('fops', []):
                                        item_url = fop.get('product', {}).get('simplifiedBopUrl')

                                        if item_url:
                                            item_urls.append(urlparse.urljoin(response.url, item_url))
                                        else:
                                            sku = fop.get('sku')

                                            if sku:
                                                skus.append(sku)
                            except:
                                self.logger.error('Wrong JSON data: {}'.format(traceback.format_exc()))

                        if skus:
                            self.logger.info('Loading {} SKUs: {}'.format(len(skus), skus))

                            try:
                                products = requests.get('https://www.ocado.com/webshop/products',
                                                        params={'skus': ','.join(skus)},
                                                        timeout=60).json()

                                self.logger.info('Got {} products'.format(len(products)))

                                for sku, product in products.iteritems():
                                    item_url = product.get('product', {}).get('simplifiedBopUrl')

                                    if item_url:
                                        item_urls.append(urlparse.urljoin(response.url, item_url))
                                    else:
                                        self.logger.warn('Product has not url: {}'.format(json.dumps(product, indent=2)))
                                        item_urls.append(self.item_url_template.format(sku=sku))
                            except:
                                self.logger.error('Could not load products: {}'.format(traceback.format_exc()))
                                item_urls.extend(self.item_url_template.format(sku=sku) for sku in skus)

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()

                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_urls_writer.writerow([item_url.split(';')[0]])

                        break
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')
