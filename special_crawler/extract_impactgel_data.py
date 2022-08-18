import urllib
import re

from extract_data import Scraper

class ImpactgelScraper(Scraper):
    """Implements methods that each extract an individual piece of data for walmart.com
        Attributes:
            product_page_url (inherited): the URL for the product page being scraped
        Static attributes:
            DATA_TYPES (dict): 
            DATA_TYPES_SPECIAL (dict):  structures containing the supported data types to be extracted as keys
                                        and the methods that implement them as values

            INVALID_URL_MESSAGE: string that will be used in the "InvalidUsage" error message,
                                 should contain information on what the expected format for the
                                 input URL is.
    """

    INVALID_URL_MESSAGE = "Expected URL format is http://shop.impactgel.com/<product-name>.htm"

    def check_url_format(self):
        return not not re.match("http://shop\.impactgel\.com/[a-zA-Z0-9\-]+\.htm", self.product_page_url)

    # ! may throw exception if not found
    def _product_name(self):
        """Extracts product name
        Returns:
            string containing product name
        """

        return self.tree_html.xpath("//div[@class='product-detail-header']/h1/text()")[0].strip()

    # ! may throw exception if not found
    def _page_title(self):
        """Extracts page title
        Returns:
            string containing page title
        """

        return self.tree_html.xpath("//title/text()")[0].strip()

    # ! may throw exception if not found
    def _model(self):
        """Extracts product model, from "Item #:" info on product page
        Returns:
            string containing product model
        """
        # get direct text from node that has a child with direct text "Item: #"
        return self.tree_html.xpath("//*[text()='Item #:']/../text()")[0].strip()

    def _features(self):
        """Extracts product features
        Returns:
            string containing product features, separated by newlines
            or None if not found
        """

        # get each feature line, join feature name and value into a line, then join all lines separated by "\n"
        features_lines = self.tree_html.xpath("//div[@class='product-details']//li")
        features_text = "\n".join(map(lambda node: "".join(node.xpath(".//text()")), features_lines))
        if features_text:
            return features_text

        return None

    def _feature_count(self):
        """Extracts number of product features
        Returns:
            int containing number of features
        """

        return len(self.tree_html.xpath("//div[@class='product-details']//li"))

    def _description(self):
        """Extracts product description
        Returns:
            string containing product description
            or None if not found
        """

        description_text = "\n".join(self.tree_html.xpath("//div[starts-with(@class,'product-description')]//text()")).strip()
        if description_text:
            return description_text

        return None

    # ! may throw exception if not found
    def _categories(self):
        """Extracts full path of hierarchy of categories
        this product belongs to, from the lowest level category
        it belongs to, to its top level department
        Returns:
            list of strings containing full path of categories
            (from highest-most general to lowest-most specific)
            or None if list is empty of not found
        """

        # eliminate "Home" root
        return self.tree_html.xpath("//a[starts-with(@class,'breadcrumb')]//text()")[1:]

    # ! may throw exception if not found
    def _category_name(self):
        """Extracts lowest level (most specific) category this product
        belongs to.
        Returns:
            string containing product category
        """

        return self.tree_html.xpath("//a[starts-with(@class,'breadcrumb')]//text()")[-1]


    # ! may return exception if not found
    def _brand(self):
        """Extracts product manufacturer, taken from product features
        Returns:
            string containing product manufacturer
        """

        # get direct text from node that has a child with direct text "Item: #"
        return self.tree_html.xpath("//*[text()='Manufacturer:']/../text()")[0].strip()

    def _htags(self):
        """Extracts 'h' tags in product page
        Returns:
            dictionary with 2 keys:
            h1 - value is list of strings containing text in each h1 tag on page
            h2 - value is list of strings containing text in each h2 tag on page
        """

        htags_dict = {}

        h1_tags = self.tree_html.xpath("//h1//text()")
        h2_tags = self.tree_html.xpath("//h2//text()")

        htags_dict['h1'] = h1_tags
        htags_dict['h2'] = h2_tags

        return htags_dict

    # ! may throw exception if not found
    def _keywords(self):
        """Extracts keywords for current product, usually from meta tag.
        Returns:
            string containing keywords
        """

        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    # ! may throw exception if not found
    def _image_urls(self):
        """Extracts urls of product images
        Returns:
            list of strings containing image urls
            or None if none found
        """

        # get onclick text from thumbnail strip of images
        thumbnail_strip = self.tree_html.xpath("//div[@class='filmstrip-thumbnails']//a/@onclick")

        # extract second argument of showPreview() function
        # in onclick action
        # (there are 2 arguments - first is regular sized image,
        # second is zoomed)
        def extract_second_image(onclick_text):
            m = re.match("showPreview\(\'(.*?)','(.*?)'\); .*", onclick_text)
            try:
                return m.group(2)
            except Exception:
                return None

        image_relative_urls = filter(None, map(extract_second_image, thumbnail_strip))
        # add domain to relative url
        image_list = map(lambda relative_url: "http://shop.impactgel.com" + relative_url, image_relative_urls)

        if image_list:
            return image_list


        # then maybe there is only one image, try to extract that
        # example: http://shop.impactgel.com/English-Contour-Felt-Pad-EC2F.htm
        return [
            "http://shop.impactgel.com" + 
            self.tree_html.xpath("//div[@class='product-image']/img/@src")[0]
            ]

    def _image_count(self):
        """Counts images available for this product
        Returns:
            int containing number of images
        """

        try:
            product_images = self._image_urls()
            return len(product_images)

        except Exception:
            pass

        # there were no images so extractor function returned exception
        return 0

    # ! may throw exception if not found
    def _video_urls(self):
        """Extracts video urls for this product
        Returns:
            list of strings containing video urls
        """

        # Videos are youtube embedded videos
        # in iframes

        iframes_urls = self.tree_html.xpath("//iframe/@src")

        # turn embed links into youtube links
        def embed_to_youtube_link(embed_link):
            # remove query string parameters
            youtube_link = urllib.splitquery(embed_link)[0]
            # replace "embed" with youtube link path
            youtube_link = re.sub("/embed/", "/watch?v=", youtube_link)
            return youtube_link

        youtube_urls = map(embed_to_youtube_link, iframes_urls)

        # TODO: any other forms of videos besides youtube?
        
        return youtube_urls

    def _video_count(self):
        """Counts number of videos available for this product
        Returns:
            int containing nr of videos
        """

        try:
            video_urls = self._video_urls()
            return len(video_urls)
        except:
            pass

        # extractor function threw exception so
        # no videos were found
        
        return 0

    # ! may throw exception if not found
    def _price(self):
        """Extracts product list price.
        Returns:
            string containing price
            (including currency)
        """

        return self.tree_html.xpath("//span[@id='listPrice']/text()")[0]

    # ! may throw exception not found
    def _unavailable(self):
        """Extracts product availability
        Returns:
            1 if product out of stock, 0 otherwise
        """

        # example out of stock product: http://shop.impactgel.com/Cowtown-Saddle-Pad-Blk-Cream-White-Fleece-36x34-1332-6.htm

        availability = self.tree_html.xpath("//span[@id='prodAvailStatus']/text()")[0]

        if availability == "Out-of-Stock":
            return 1
        else:
            return 0


    def _owned(self):
        return 1

    def _marketplace(self):
        return 0

    DATA_TYPES = {
        "product_name" : _product_name, \
        "product_title": _product_name, \
        "title_seo" : _page_title, \
        "model" : _model, \
        # "upc" : _upc, \

        "features": _features, \
        "feature_count" : _feature_count, \
        # "model_meta" : _model_meta, \
        "description" : _description, \
        # "long_description": _long_description, \
    
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand,

        # "mobile_image_same" 
        "image_count" : _image_count, \
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        # "pdf_count" : _pdf_count, \
        # "pdf_urls" : _pdf_urls, \
        # "webcollage"
        "htags" : _htags, \
        "keywords" : _keywords, \

        "price" : _price, \
        "marketplace": _marketplace, \
        "owned" : _owned, \
        "owned_out_of_stock" : _unavailable, \

        # # What are these supposed to be?
        # "in_stores"
        # "in_stores_only"
        # "owned" -> default 1
        # "marketplace" -> default 0
        # "marketplace_sellers"
        # "marketplace_lowest_price"
        
    }