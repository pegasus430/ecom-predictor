from lxml import html
import itertools

class QuillVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        choices = self.tree_html.xpath('//div[contains(@class, "MultiChoiceNew")]')
        attributes = self.tree_html.xpath('//div[contains(@class, "MultiChoiceNew")]'
                                          '//div[@class="clear ST_m formLabel txtBold"]'
                                          '/text()')
        attributes_values_list = []
        variants_list = []

        for choice in choices:
            attributes_values = choice.xpath('.//select/option[position()>1]/text()')
            attributes_values_list.append(attributes_values)

        combination_list = list(itertools.product(*attributes_values_list))

        for value in combination_list:
            variant = {
                'properties': {}
            }
            in_stock = 1
            selected = 1
            for idx, key in enumerate(attributes):
                variant['properties'][key] = value[idx]
                if self.tree_html.xpath('//div[contains(@class, "MultiChoiceNew")]'
                                        '//select'
                                        '/option[@class="disabled" and text()="' + value[idx] + '"]'):
                    in_stock *= 0
                if not self.tree_html.xpath('//div[contains(@class, "MultiChoiceNew")]'
                                            '//select'
                                            '/option[@selected="selected" and text()="' +
                                            value[idx] + '"]'):
                    selected *= 0
            variant['in_stock'] = bool(in_stock)
            variant['selected'] = bool(selected)
            variants_list.append(variant)
        return variants_list
