import csv
import traceback

import requests


class AmazonChannel(object):

    ch_scraper_url = 'http://chscraper.contentanalyticsinc.com/get_data'

    max_retries = 5

    def __init__(self, input_file):
        self.urls = self._read_input_file(input_file)
        self.output_type = 'text/csv'

    def _read_input_file(self, input_file):
        with open(input_file, 'rU') as f:
            input_csv = csv.reader(f)

            for row in input_csv:
                yield row[0]

    def write(self, value):
        return value

    def convert(self):
        output_csv = csv.writer(self)

        yield output_csv.writerow(['Core', 'Pantry', 'Error'])

        results = self._check(self.urls)

        for result in results:
            yield output_csv.writerow(result)

    def _check(self, urls):
        core = []
        pantry = []
        error = []

        for url in urls:
            for _ in range(self.max_retries):
                try:
                    response = requests.get(self.ch_scraper_url, params={'url': url}, timeout=120)

                    if response.status_code == requests.codes.ok:
                        data = response.json()

                        if data.get('page_attributes', {}).get('pantry'):
                            pantry.append(url)
                        else:
                            core.append(url)

                        break
                except:
                    print traceback.format_exc()
            else:
                error.append(url)

        return map(None, core, pantry, error)
