import csv
import requests
import traceback
import time
import re
import json

from urlparse import urlparse
from . import SitemapSpider, SitemapSpiderError


class WayfairSitemapSpider(SitemapSpider):
    retailer = 'wayfair.com'

    headers = {
        'User-Agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
    }

    def task_item_to_variant_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        item_urls = options.get('urls', [])

        with open(self.get_file_path_for_result('variants.csv'), 'w') as item_urls_file:
            item_urls_csv = csv.writer(item_urls_file)
            item_urls_csv.writerow(['Item URL', 'Variant URL'])

            failed_urls = []
            for item_url in item_urls:
                try:
                    self.logger.info('Scraping item url: {}'.format(item_url))

                    for i in range(self.max_retries):
                        try:
                            response = requests.get(item_url, timeout=60, headers=self.headers)
                        except:
                            self.logger.error('Error: {}'.format(traceback.format_exc()))
                            self.logger.info('Try again in {} seconds'.format(i + 1))
                            time.sleep(i + 1)
                        else:
                            break
                    else:
                        raise SitemapSpiderError('Failed after retries')

                    self._check_response(response, raise_error=True)

                    variants = self._parse_variants(response.content)

                    if variants:
                        item_url_parts = urlparse(item_url)

                        for variant in variants:
                            variant_url = '{item_url}{sign}piid={variant}'.format(
                                item_url=item_url,
                                sign='&' if item_url_parts.query else '?',
                                variant=variant)

                            item_urls_csv.writerow([item_url, variant_url])
                    else:
                        item_urls_csv.writerow([item_url, item_url])
                except:
                    self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                    failed_urls.append(item_url)
            if failed_urls:
                self.save_failed_urls(failed_urls)
                raise SitemapSpiderError('Some urls cannot be processed')

    def _parse_variants(self, content):
        items = re.findall(
            'wf\.extend\(({.*?})\);',
            content
        )

        for item in items:
            try:
                item_data = json.loads(item)
            except:
                self.logger.warn('Can not parse item: {}'.format(traceback.format_exc()))
            else:
                for value in item_data.get('wf').get('reactData', {}).values():
                    standard_options = value.get('bootstrap_data', {}).get('options', {}).get('standardOptions')

                    if standard_options:
                        return [option['option_id'] for option in standard_options[0].get('options', [])]
