import urlparse
import re
import json
import sys
from itertools import chain

from lxml.etree import tostring

from extract_data import Scraper





#region Helper functions
def apikey(key):
    def _decorator(func):
        func.apikey = key
        return func

    return _decorator


#endregion

class VitadepotScraper(Scraper):

    def __init__(self, **kwargs):
        for method in map(lambda name: getattr(self.__class__, name), dir(self)):
            if hasattr(method, 'apikey'):
                self.DATA_TYPES[method.apikey] = method

        Scraper.__init__(self, **kwargs)

    #region API methods
    @apikey('id')
    def _extract_product_id(self):
        return self.tree_html.xpath('//div[@class="no-display"]/input[@name="product"]/@value')[0]

    @apikey('name')
    def _product_name_from_tree(self):
        return self.tree_html.xpath('//div[@class="product-name"]/h1')[0].text

    @apikey('keywords')
    def _meta_keywords_from_tree(self):
        return self.tree_html.xpath('//meta[@name="keywords"]')[0].get('content')

    @apikey('short_desc')
    def _short_description_from_tree(self):
        return self.tree_html.xpath('//meta[@name="description"]')[0].get('content')

    @apikey('long_desc')
    def _long_description_from_tree(self):
        elt = ''.join(map(tostring, self._find_description_elts()))
        return elt

    @apikey('price')
    def _price_from_tree(self):
        return self.tree_html.cssselect('.price')[0].text.strip()

    @apikey('features')
    def _features_from_tree(self):
        return [feature for feature in self._scrape_features() if not self._find_sku([feature])]

    @apikey('nr_features')
    def _nr_features_from_tree(self):
        features = self._scrape_features()
        return len(features) - (self._find_sku(features) and 1 or 0)

    @apikey('anchors')
    def _anchors_from_tree(self):
        link_list = [{'href': link.get('href'), 'text': link.text} for link in
                     chain(*(child.findall('a') for child in self._find_description_elts()))]
        return {'quantity': len(link_list), 'links': link_list}

    @apikey('htags')
    def _htags_from_tree(self):
        tags = [[], 'h1', 'h2', 'h3', 'h4']
        htags_list = [tag.text for tag in chain(*(reduce(lambda a, b: a + child.findall(b), tags)
                                                  for child in self._find_description_elts()))]
        return {'quantity': len(htags_list), 'tags': htags_list}

    @apikey('brand')
    def _brand_from_tree(self):
        return self.tree_html.cssselect('.view-more-cat a')[0].text

    @apikey('image_url')
    def _image_url(self):
        result = self.tree_html.xpath('//*[@class="MagicThumb"]/img')[0]
        return result.get('src')

    @apikey('product_images')
    def _product_images(self):
        return len(self.tree_html.xpath('//*[@class="MagicThumb"]/img'))

    @apikey('title')
    def _title_from_tree(self):
        return self.tree_html.cssselect('title')[0].text.strip(' \n')

    @apikey('all_depts')
    def _crumbs_from_tree(self):
        breadcrumbs = self._extract_breadcrumbs()
        return [{'level': level + 1, 'url': bc['url'], 'text': bc['text']} for level, bc in enumerate(breadcrumbs)]

    @apikey('dept')
    def _dept_from_tree(self):
        return self._extract_breadcrumbs()[-1]

    @apikey('super_dept')
    def _super_dept_from_tree(self):
        return self._extract_breadcrumbs()[0]

    @apikey('sku')
    def _sku_from_tree(self):
        return self._find_sku(self._scrape_features())

    #endregion

    #region Helper methods
    def check_url_format(self):
        #scheme, netloc, path, query, fragment = urlparse.urlsplit(self.product_page_url)
        return re.match('http://vitadepot\.com/[^/]+\.html', self.product_page_url)
        #return scheme == 'http' and re.match('(www)?vitadepot.com', netloc) and re.match('.+?.html', path) and not \
        #    (query or fragment)

    def _scrape_features(self):
        return map(lambda s: s.text.strip(), self.tree_html.cssselect('.extratributes ul li span'))

    def _find_description_elts(self):
        return self.tree_html.xpath('//*[@id="product_tabs_description_tabbed_contents"]/div[@class="std"]/*')

    def _find_sku(self, features):
        sku = next(iter(filter(None, (re.match('SKU #(\d+)', ftr) for ftr in features))), None)
        return sku.groups()[0] if sku else None

    def _extract_breadcrumbs(self):
        bc = self.tree_html.cssselect('.breadcrumbs ul li a')
        links = ((a.get('href'), a.text) for a in bc)
        return [{'url': url, 'text': text} for url, text in links if len(urlparse.urlparse(url).path) > 1]

    def main(self, *args):
        if not self.check_url_format():
            raise Exception(self.INVALID_URL_MESSAGE)
        return json.dumps(self.product_info(args))

    #endregion

    #region Data
    DATA_TYPES = {
    }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = {
        'seller': lambda self: {'marketplace': 1, 'owned': 1},
        'pdf_url': lambda self: None,
        'total_reviews': lambda self: 0,  # None found so far
    }

    INVALID_URL_MESSAGE = "Expected URL format is http://vitadepot.com/<product-name>.html"
    #endregion
    #--VitadepotScraper


if __name__ == "__main__":
    scraper = VitadepotScraper(sys.argv[1])
    args = sys.argv[2:]
    print scraper.main(*args)