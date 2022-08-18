import csv
import re

from . import SitemapSpider


class ModclothSitemapSpider(SitemapSpider):
    retailer = 'modcloth.com'

    SITEMAP_URL = 'https://www.modcloth.com/sitemap.xml'

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        products_seen = set()

        with open(self.get_file_path_for_result('modcloth_products.csv'), 'wb') as urls_file:
            urls_csv = csv.writer(urls_file)

            for url in self._parse_sitemap(self.SITEMAP_URL):
                product_id = re.search(r'modcloth\.com/(?:.*/)?(\d+)\.html', url)

                if product_id:
                    product_id = int(product_id.group(1))

                    if product_id not in products_seen:
                        products_seen.add(product_id)

                        urls_csv.writerow([url])

        urls_file.close()
