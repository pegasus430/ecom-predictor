import lxml.html
from itertools import product


class FlipkartVariants(object):
    def setupSC(self, response):
        """ Call it from SC spiders """
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _variants(self):
        variants_section = self.tree_html.cssselect(
            '.multiSelectionWrapper > .omniture-field')
        if not variants_section:
            return None
        options_str = variants_section[0].attrib['data-prop36']
        if not options_str:
            return None
        selected_values = self.tree_html.cssselect(
            '.multiSelectionWidget-selector.selected')
        key_name = 'selector-attr-'
        selected = {}
        for s_v in selected_values:
            selected_key = [k.strip()[len(key_name):]
                            for k in s_v.attrib['class'].split(' ')
                            if k.startswith(key_name)]
            if not selected_key:
                continue
            selected_key = selected_key[0]
            selected_value = s_v.cssselect('[data-selectorvalue]')
            if not selected_value:
                continue
            selected_value = selected_value[0].attrib['data-selectorvalue']
            selected[selected_key] = selected_value

        # string looks like "color:Black,Champagne;storage:16 GB"
        available_options = options_str.split(';')
        options = {}
        for ao in available_options:
            tmp = ao.split(':')
            tmp[1] = tmp[1].replace(', ', '|||').split(',')
            options[tmp[0]] = [_.replace('|||', ', ') for _ in tmp[1]]
        if not options:
            return None
        variants_list = list(product(*options.values()))
        keys = options.keys()
        variants = []
        for variant_item in variants_list:
            variant = {}
            for i, key in enumerate(keys):
                variant[key] = variant_item[i]
            variants.append(variant)
        final_variants = [
            {'price': None, 'selected': v == selected, 'properties': v}
            for v in variants
        ]
        return final_variants