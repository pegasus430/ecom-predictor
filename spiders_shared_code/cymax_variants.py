import re
import json
import traceback
import lxml.html

try:
    from scrapy import log
    scrapy_imported = True
except:
    scrapy_imported = False


class CymaxVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    @staticmethod
    def _get_xpath_value(obj, xpath_exp, default_value=''):
        val = obj.xpath(xpath_exp)
        return val[0] if val else default_value

    def _variants(self):
        variants = []
        variants_data = self.tree_html.xpath(
            '//ul[contains(@class,"product-options-list")]//a'
        )
        option_name = self._get_xpath_value(
            self.tree_html,
            '//div[@id="product-options"]//h5/text()'
        ).replace('Select', '').strip()
        if option_name:
            for variant in variants_data:
                option_value = self._get_xpath_value(variant, './parent::li/span/text()')
                variants.append(
                    {
                        "image_url": self._get_xpath_value(variant, './@img', None),
                        "price": float(self._get_xpath_value(variant, './@price', 0.0)),
                        "properties": {
                            option_name: option_value
                        },
                        "selected": "active" in self._get_xpath_value(variant, './@class'),
                        "in_stock": self._get_xpath_value(variant, './@price') != '',
                    }
                )

        return variants if variants else None
