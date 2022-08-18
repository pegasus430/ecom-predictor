import csv
import re

from . import SitemapSpider


class ShoesSitemapSpider(SitemapSpider):
    retailer = 'shoes.com'

    SITEMAP_URL = 'https://www.shoes.com/sitemap.xml'

    def task_sitemap_to_item_urls(self, options):
        self.logger.info('Start parsing sitemap: {}'.format(self.SITEMAP_URL))

        products_seen = set()

        with open(self.get_file_path_for_result('shoes_products.csv'), 'wb') as urls_file:
            urls_csv = csv.writer(urls_file)

            for url in self._parse_sitemap(self.SITEMAP_URL):
                product_id = re.search(r'shoes\.com/(?:.*/)?(\d+)', url)

                if product_id:
                    product_id = int(product_id.group(1))

                    if product_id not in products_seen:
                        products_seen.add(product_id)

                        urls_csv.writerow([url])

        urls_file.close()
