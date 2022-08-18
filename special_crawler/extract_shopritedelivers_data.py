import re
import urlparse
from extract_data import Scraper


class ShopritedeliversScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is ^http//www.shopritedelivers.com/.+?\.aspx$"

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match('^http:\/\/www\.shopritedelivers\.com\/.+?\.aspx$', self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        try:
            if not self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]'):
                raise Exception()
        except Exception:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_id = self.tree_html.xpath('//*[@itemprop="sku"]/text()')[0].strip()
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        title = self.tree_html.xpath('//*[@itemprop="name"]//text()')
        return " ".join(title).strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath('//title/text()')[0].strip()

    def _description(self):
        description = self.tree_html.xpath('//*[@itemprop="description"]//text()')
        description = [_d.strip() for _d in description]
        return " ".join(description).strip()

    def _long_description(self):
        return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _mobile_image_same(self):
        return None

    def _canonical_link(self):
        return self.tree_html.xpath('//link[@rel="canonical"]/@href')[0]

    def _image_urls(self):
        image_url = self.tree_html.xpath(
            '//*[@id="ProductImageUrl"]/@href')
        image_urls = self.tree_html.xpath(
            '//div[@class="additionalImages"]'
            '/div[@class="thumbnailsList"]//li/a/@href'
        )
        if not image_urls:
            image_urls = image_url
        return [urlparse.urljoin(self.product_page_url, url) for url in image_urls
                if '/Assets/ProductImages/ImageComingSoon_t.jpg' not in url]

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())
        return 0

    def _video_urls(self):
        return None

    def _video_count(self):
        return None

    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        return None

    def _no_image(self):
        return None

    def _webcollage(self):
        return None

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('*//*[@itemprop="price"]/text()')[0].strip()
        return price

    def _price_amount(self):
        return float(self._price().replace('$', ''))

    def _price_currency(self):
        return 'USD'

    def _in_stores_only(self):
        return None

    def _owned(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_only(self):
        return 1

    def _in_stores(self):
        return 0

    def _in_stores_only(self):
        return 0

    def _site_online_out_of_stock(self):
        return 0

    def _owned_out_of_stock(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_out_of_stock(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    def _web_only(self):
        return 1

    def _no_longer_available(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories_names = self.tree_html.xpath(
            '//*[@class="breadCrumbs categoryBreadCrumbs"]//a/text()'
        )[1:]
        return categories_names

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        brand = self.tree_html.xpath('//*[@itemprop="manufacturer"]/text()')
        return brand[0] if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "url": _url, \
        "product_id": _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo, \
        "description": _description, \
        "long_description": _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count": _image_count, \
        "image_urls": _image_urls, \
        "video_count": _video_count, \
        "video_urls": _video_urls, \
        "no_image": _no_image, \
        "pdf_count": _pdf_count, \
        "pdf_urls": _pdf_urls, \
        "webcollage": _webcollage, \
        "htags": _htags, \
        "keywords": _keywords, \
        "canonical_link": _canonical_link,

        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency" : _price_currency, \
        "owned" : _owned, \
        "marketplace" : _marketplace, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores" : _in_stores, \
        "owned_out_of_stock": _owned_out_of_stock, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_out_of_stock": _marketplace_out_of_stock, \
        "web_only": _web_only, \
        "no_longer_available": _no_longer_available, \

        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "category_name": _category_name, \
        "brand": _brand, \
        }