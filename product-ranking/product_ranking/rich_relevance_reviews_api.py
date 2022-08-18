import re
import hjson
from urlparse import urlparse, parse_qs
from product_ranking.spiders import cond_set_value
from product_ranking.items import RelatedProduct


class RichRelevanceApi(object):
    def __init__(self, response, product, base_url):
        self.response = response
        self.base_url = base_url
        self.product = product

    def parse_related_products(self):
        """parse response from richrelevance api"""
        body = re.sub('\t|\s{2,6}', '', self.response.body)  # strip tabs
        initial_data = re.findall('json\s?=\s?(\{.+?\});', body)
        initial_data = [re.sub('\t|\s{2,6}', '', _) for _ in initial_data]
        initial_data = [hjson.loads(_) for _ in initial_data]
        additional_data = re.findall(
            '\[(\d+)\]\.json\.items\.push\((\{.+?\})\);', body)
        for ind, data in additional_data:
            initial_data[int(ind)]['items'].append(hjson.loads(data))
        related_products = []
        for data in initial_data:
            l = []
            for item in data['items']:
                title = item.get('name', '')
                url = item.get('link_url', '')
                if not title or not url:
                    continue
                url = parse_qs(urlparse(url).query).get('ct', [''])[0]
                if not url:
                    continue
                if url.startswith('/'):
                    url = '%s%s' % (self.base_url, url)
                l.append(RelatedProduct(title=title, url=url))
            if l:
                related_products.append({data['message']: l})
        cond_set_value(self.product, 'related_products', related_products)