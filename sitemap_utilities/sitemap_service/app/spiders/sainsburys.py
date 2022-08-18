import csv
import requests
import uuid
import urlparse
import urllib
import traceback
import re

from lxml import etree

from . import SitemapSpider, SitemapSpiderError


class SainsburysCoUkSitemapSpider(SitemapSpider):
    retailer = 'sainsburys.co.uk'

    shelf_url_template = "http://www.sainsburys.co.uk/webapp/wcs/stores/servlet/AjaxApplyFilterBrowseView?" \
                         "langId=44&storeId=10151&catalogId=10241&categoryId={categoryid}" \
                         "&parent_category_rn={top_category}&top_category={top_category}" \
                         "&pageSize=36&orderBy={orderby}&searchTerm=&beginIndex={beginindex}&requesttype=ajax"

    required_params = ['categoryid', 'top_category', 'orderby', 'beginindex']

    session = requests.session()

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

                    current_page = 0

                    format_parameters = self._parse_required_url_parameters(
                        shelf_url,
                        self.required_params
                    )

                    if format_parameters:
                        shelf_url = self.shelf_url_template.format(**format_parameters)
                    else:
                        shelf_url = self._extract_url_data(shelf_url)

                    while True:
                        self.logger.info('Scraping shelf page: {}'.format(shelf_url))

                        response = self.session.get(shelf_url, timeout=60)

                        self._check_response(response, raise_error=True, session=self.session)

                        item_urls = []
                        total = 0

                        for data in response.json():
                            if data.get('productLists'):
                                product_links_info = data['productLists'][0].get('products', [])

                                for link_info in product_links_info:
                                    link_tree = etree.HTML(link_info.get('result', ''))
                                    link_by_html = link_tree.xpath('//li[@class="gridItem"]//h3/a/@href')

                                    if link_by_html:
                                        item_urls.append(link_by_html[0])

                            if data.get('pageHeading'):
                                total = int(re.search('(\d+)', data['pageHeading'], re.DOTALL).group(1))
                                self.logger.info('Total items: {}'.format(total))

                        if not item_urls:
                            dump_filename = uuid.uuid4().get_hex()

                            self.logger.warn('Empty items list, check dump: {}'.format(dump_filename))
                            self._save_response_dump(response, dump_filename)

                        self.logger.info('Found {} items at page'.format(len(item_urls)))

                        for item_url in item_urls:
                            item_urls_writer.writerow([urlparse.urljoin(response.url, item_url)])

                        current_page += 1

                        format_parameters = self._parse_required_url_parameters(
                            shelf_url,
                            self.required_params
                        )

                        begin_index = 36 * current_page

                        if format_parameters and begin_index < total:
                            format_parameters['beginindex'] = begin_index
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

    def _extract_url_data(self, shelf_url):
        self.logger.info('Extracting required params')

        try:
            response = self.session.get(shelf_url, timeout=60)

            tree = etree.HTML(response.content)

            format_parameters = {
                param: tree.xpath(
                    '//input[@type="hidden" and translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ",'
                    '"abcdefghijklmnopqrstuvwxyz")="{}"]/@value'.format(param))[0]
                for param in self.required_params
            }
            if format_parameters:
                shelf_url = self.shelf_url_template.format(**format_parameters)
        except:
            self.logger.error('Can not extract required params: {}'.format(traceback.format_exc()))

        return shelf_url
