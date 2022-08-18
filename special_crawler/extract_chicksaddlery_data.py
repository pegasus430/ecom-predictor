from lxml import html, etree
import re

from extract_data import Scraper

class ChicksaddleryScraper(Scraper):
    """Implements methods that each extract an individual piece of data for chicksaddlery.com
    """

    INVALID_URL_MESSAGE = "Expected URL format is http://www.chicksaddlery.com/page/CDS/[a-zA-Z0-9/]*"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match("http://www\.chicksaddlery\.com/page/CDS/[a-zA-Z0-9/]*", self.product_page_url)
        return not not m

    # ! may throw exception if not found
    def _product_name(self):
        """Extracts product name from heading tag on product page
        Returns:
            string containing product name
        """
        return self.tree_html.xpath("//h1/text()")[0].strip()

    # ! may throw exception if not found
    def _page_title(self):
        """Extracts page title
        Returns:
            string containing page title
        """

        return self.tree_html.xpath("//title/text()")[0].strip()

    # ! may throw exception if not found
    def _model(self):
        """Extracts product model (or "product code" as this site calls it)
        Returns:
            string containing model
        """

        return self.tree_html.xpath("""//td[@id='main-content']
            /div[starts-with(@class, 'product-details')]/div[@class='product-code']/span
            /text()""")[0].strip()

    # TODO: test on more examples
    def _features(self):
        """Extracts product features
        Returns:
            string containing product features (separated by newlines)
            or None if not found
        """

        features = "".join(self.tree_html.xpath("//h2[text()='Features']/following-sibling::li/text()"))
        if features:
            return features
        else:
            return None

    def _feature_count(self):
        """Extracts number of features
        Returns:
            int representing number of features
        """

        return len(self.tree_html.xpath("//h2[text()='Features']/following-sibling::li"))

    def _description(self):
        """Extracts product description text
        Returns:
            string containing product description
            or None if description not found or empty
        """

        # TODO: This aims to only extract the first part of the description.
        #       Does it do it correctly for many examples?
        description_node = self.tree_html.xpath(\
            "//div[@class='product-description']/text()[normalize-space()!=''] | " + \
            "//div[@class='product-description']/h4//text()[normalize-space()!='']"
            )

        description_text = "".join(description_node).strip()

        if description_text:
            return description_text
        else:
            return None

    def _long_description(self):
        """Extracts product long description text
        Returns:
            string containing product long description
            or None if description not found or empty
        """

        description_node = self.tree_html.xpath(\
            "//div[@class='product-description']/p/text()[normalize-space()!='']" \
            )

        description_text = "".join(description_node).strip()

        if description_text:
            return description_text
        else:
            return None

    def _image_urls(self):
        """Extracts image urls for this product
        Returns:
            list of strings representing urls of images
            or None if no image found
        """

        base_url = "http://www.chicksaddlery.com/Merchant2/"
        images = self.tree_html.xpath("//div[@class='product-image']/img/@src")

        if images:
            return map(lambda relative_url: base_url + relative_url, images)
        else:
            return None

    def _image_count(self):
        """Extracts number of images for this product
        Returns:
            int representing number of images
        """

        return len(self.tree_html.xpath("//div[@class='product-image']/img"))

    def _htags(self):
        """Extracts <h1> and <h2> tags on the product page
        Returns:
            dictionary with "h1" and "h2" as keys,
            and lists with each heading's text as values
        """

        h1s = self.tree_html.xpath("//h1//text()")
        h2s = self.tree_html.xpath("//h2//text()")

        return {
        "h1" : h1s,
        "h2" : h2s,
        }

    # ! may throw exception if not found
    def _keywords(self):
        """Extracts keywords related to product, from
        "meta" tag
        Returns:
            string containing keywords
        """

        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    # ! might throw exception if not found
    def _price(self):
        """Extracts (main) price on product page
        Returns:
            string containing product price, including currency
        """

        return self.tree_html.xpath("""//td[@id='main-content']
            /div[starts-with(@class,'product-details')]
            /div[@class='product-price']//strong/text()""")[0]

    # ! may throw exception if not found
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

        categories_full = self.tree_html.xpath("//div[@id='page-header']/a/text()")

        # eliminate "Home"
        categories = categories_full[1:]

        if categories:
            return categories
        else:
            return None

    # ! may throw exception if not found
    def _category(self):
        """Extracts lowest level (most specific) category this product
        belongs to.
        Works for both old and new pages
        Returns:
            string containing product category
        """

        return self.tree_html.xpath("//div[@id='page-header']/a/text()")[-1]

    def _owned(self):
        return 1

    def _marketplace(self):
        return 0

    DATA_TYPES = {
        "product_name" : _product_name, \
        "product_title" : _product_name, \
        "title_seo" : _page_title, \
        "model" : _model, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "long_description" : _long_description, \
        "image_count" : _image_count, \
        "image_urls" : _image_urls, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "price" : _price, \
        "marketplace": _marketplace, \
        "owned" : _owned, \
        "categories" : _categories_hierarchy, \
        "category_name" : _category, \
    }