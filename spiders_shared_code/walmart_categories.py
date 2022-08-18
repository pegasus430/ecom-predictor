import re
import json
import string
import urlparse

import lxml.html


class WalmartCategoryParser:

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def full_categories_with_links(self, domain='walmart.com'):
        result = []
        categories_list = self.tree_html.xpath(
            "//*[contains(@class, 'prod-breadcrumb')]//li[@class='breadcrumb']/.//a")
        if not categories_list:
            categories_list = self.tree_html.xpath("//li[@class='breadcrumb']/.//a")
        for a in categories_list:
            url = a.xpath('./@href')[0]
            if not url.startswith('http'):
                url = urlparse.urljoin('http://'+domain, url)
            arr = a.xpath('.//*//text()')
            if len(arr) > 0:
                name = arr[0]
            else:
                name = ''
            result.append({
                'name': name,
                'url': url
            })
        return result

    def _categories_hierarchy(self):
        """Extracts full path of hierarchy of categories
        this product belongs to, from the lowest level category
        it belongs to, to its top level department.
        Works for both old and new page design
        Returns:
            list of strings containing full path of categories
            (from highest-most general to lowest-most specific)
            or None if list is empty of not found
        """

        # assume new page design
        categories_list = self.tree_html.xpath("//li[@class='breadcrumb']/.//a/span/text()")
        if categories_list:
            return categories_list
        else:
            # assume old page design
            try:
                return self._categories_hierarchy_old()
            except Exception:
                return None

    # ! may throw exception if not found
    def _categories_hierarchy_old(self):
        """Extracts full path of hierarchy of categories
        this product belongs to, from the lowest level category
        it belongs to, to its top level department.
        For old page design
        Returns:
            list of strings containing full path of categories
            (from highest-most general to lowest-most specific)
            or None if list is empty of not found
        """

        js_breadcrumb_text = self.tree_html.xpath("""//script[@type='text/javascript' and
         contains(text(), 'adsDefinitionObject.ads.push')]/text()""")[0]

        # extract relevant part from js function text
        js_breadcrumb_text = re.sub("\n", " ", js_breadcrumb_text)
        m = re.match('.*(\{.*"unitName".*\}).*', js_breadcrumb_text)
        json_object = json.loads(m.group(1))
        categories_string = json_object["unitName"]
        categories_list = categories_string.split("/")
        # remove first irrelevant part
        catalog_index = categories_list.index("catalog")
        categories_list = categories_list[catalog_index + 1 :]

        # clean categories names
        def clean_category(category_name):
            # capitalize every word, separated by "_", replace "_" with spaces
            return re.sub("_", " ", string.capwords(category_name, "_"))

        categories_list = map(clean_category, categories_list)
        return categories_list

    # ! may throw exception of not found
    def _category(self):
        """Extracts lowest level (most specific) category this product
        belongs to.
        Works for both old and new pages
        Returns:
            string containing product category
        """

        # return last element of the categories list

        # assume new design
        try:
            category = self.tree_html.xpath(
                "//li[@class='breadcrumb']//a/span/text()"
            )[-1]
        except Exception:
            category = None

        if category:
            return category
        else:
            # asume old design
            category = self._categories_hierarchy_old()[-1]

            return category
