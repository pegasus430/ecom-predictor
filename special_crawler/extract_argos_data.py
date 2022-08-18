__author__ = 'Lai Tash (lai.tash@yandex.ru)'

import urlparse
import json
import sys
import string
import re
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


class BaseScraper(Scraper):
    def __init__(self, **kwargs):
        for method in map(lambda name: getattr(self.__class__, name), dir(self)):
            if hasattr(method, 'apikey'):
                self.DATA_TYPES[method.apikey] = method

        Scraper.__init__(self, **kwargs)

    def main(self, *args):
        if not self.check_url_format():
            raise Exception(self.INVALID_URL_MESSAGE)
        return json.dumps(self.product_info(args))

    DATA_TYPES = {
    }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = {
    }

    INVALID_URL_MESSAGE = "Expected url format is: http://www.argos.co.uk/static/Product/partNumber/{digits}.htm"


class ArgosScraper(BaseScraper):
    # Some data would need additiona requests:
    # nr_reviews, average_reviews
    #
    # Not found:
    # brand, model

    @apikey('name')
    def _name_from_tree(self):
        return self.tree_html.cssselect('#pdpProduct h1')[0].text.strip(' \n\t')

    @apikey('keywords')
    def _keywords_from_tree(self):
        return filter(None,
                      map(string.strip, self.tree_html.cssselect('meta[name=keywords]')[0].get('content').split(',')))

    @apikey('shortdesc')
    def _shortdesc_from_treee(self):
        return self.tree_html.cssselect('.fullDetails p')[0].text

    @apikey('long_desc')
    def _desc_from_tree(self):
        desc_tree = self._extract_full_description()
        desc_elements = []
        for elt in desc_tree.getchildren():
            if elt.tag == 'ul':
                continue
            if elt.getnext() and elt.getnext().tag == 'ul':
                continue
            desc_elements.append(elt)
        return ''.join((tostring(elt) for elt in desc_elements))

    @apikey('price')
    def _price_from_tree(self):
        return self.tree_html.cssselect('.actualprice .price ')[0].text_content()

    @apikey('nr_features')
    def _nr_features_from_tree(self):
        features = self._extract_features()
        return len(list(chain(*features.values())))

    @apikey('features')
    def _features_from_tree(self):
        return self._extract_features()

    @apikey('title')
    def _title_from_tree(self):
        return self.tree_html.cssselect('title')[0].text.strip(' \n')

    @apikey('image_url')
    def _image_url_from_tree(self):
        return [urlparse.urljoin(self.product_page_url, img.get('src')) for img in
                self.tree_html.cssselect('#mainimage.photo')]

    @apikey('no_image')
    def _no_image(self):
        return not self._image_url_from_tree()


    def _extract_features(self):
        desc_tree = self._extract_full_description()
        features = {}
        current_set = None
        for elt in desc_tree.getchildren():
            if elt.tag == 'ul':
                if current_set is None:
                    current_set = []
                    features['default'] = current_set
                current_set.extend([li.text for li in elt.getchildren()])
            elif elt.tag == 'p' and elt.getnext().tag == 'ul':
                current_set = []
                features[elt.text] = current_set
        return features

    def _extract_full_description(self):
        return self.tree_html.cssselect('.fullDetails')[0]

    def check_url_format(self):
        return re.match('http://www\.argos\.co\.uk/static/Product/partNumber/\d+.htm', self.product_page_url)

if __name__ == "__main__":
    scraper = ArgosScraper(sys.argv[1])
    args = sys.argv[2:]
    print scraper.main(*args)