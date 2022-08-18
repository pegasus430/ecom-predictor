import csv
import requests
import uuid
import urlparse
import traceback

from . import SitemapSpider, SitemapSpiderError


class AhSitemapSpider(SitemapSpider):
    retailer = 'ah.nl'

    shelf_url_template = 'https://www.ah.nl/service/rest/delegate?url={path}'

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

                        path = urlparse.urlparse(shelf_url).path

                        response = requests.get(self.shelf_url_template.format(path=path), timeout=60)

                        self._check_response(response, raise_error=True)

                        item_urls = []

                        try:
                            data = response.json()

                            for lane in data.get('_embedded', {}).get('lanes', []):
                                if lane.get('type') == 'ProductLane':
                                    for item in lane.get('_embedded', {}).get('items', []):
                                        if item.get('type') == 'Product':
                                            item_url = item.get('navItem', {}).get('link', {}).get('href')

                                            if item_url:
                                                item_urls.append(urlparse.urljoin(shelf_url, item_url))
                        except:
                            self.logger.error('Wrong JSON data: {}'.format(traceback.format_exc()))

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
