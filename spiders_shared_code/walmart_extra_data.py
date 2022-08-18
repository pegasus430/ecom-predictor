#!/usr/bin/python

from lxml import html

import re
import json
import mmh3 as MurmurHash
import os
from PIL import Image
from io import BytesIO
from StringIO import StringIO
import requests


def fetch_bytes(url):
    # TODO: fix this - remove if this method is not neeeded anymore
    agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:24.0) Gecko/20140319 Firefox/24.0 Iceweasel/24.4.0'
    headers ={'User-agent': agent}
    with requests.Session() as s:
        response = s.get(url, headers=headers, timeout=15)
        if response != 'Error' and response.ok:
            img = Image.open(StringIO(response.content))
            b = BytesIO()
            img.save(b, format='png')
            data = b.getvalue()
            return data


class WalmartExtraData(object):

    # base URL for request containing video URL from webcollage
    BASE_URL_VIDEOREQ_WEBCOLLAGE = "http://json.webcollage.net/apps/json/walmart?callback=jsonCallback&environment-id=live&cpi="
    # base URL for request containing video URL from webcollage
    BASE_URL_VIDEOREQ_WEBCOLLAGE_NEW = "http://www.walmart-content.com/product/idml/video/%s/WebcollageVideos"
    # base URL for request containing video URL from sellpoints
    BASE_URL_VIDEOREQ_SELLPOINTS = "http://www.walmart.com/product/idml/video/%s/SellPointsVideos"
    # base URL for request containing video URL from sellpoints
    BASE_URL_VIDEOREQ_SELLPOINTS_NEW = "http://www.walmart-content.com/product/idml/video/%s/SellPointsVideos"
    # base URL for request containing pdf URL from webcollage
    BASE_URL_PDFREQ_WEBCOLLAGE = "http://content.webcollage.net/walmart/smart-button?ignore-jsp=true&ird=true&channel-product-id="
    # base URL for request for product reviews - formatted string
    BASE_URL_REVIEWSREQ = 'http://walmart.ugc.bazaarvoice.com/1336a/%20{0}/reviews.djs?format=embeddedhtml'
    # base URL for product API
    BASE_URL_PRODUCT_API = "http://www.walmart.com/product/api/{0}"

    INVALID_URL_MESSAGE = "Expected URL format is http://www.walmart.com/ip[/<optional-part-of-product-name>]/<product_id>"

    def __init__(self, *args, **kwargs):
        self.product_page_url = kwargs['url']
        self.tree_html = kwargs['response']

        # no image hash values
        self.NO_IMAGE_HASHES = self.load_image_hashes()
        # whether product has any sellpoints media
        self.has_sellpoints_media = False
        # product videos (to be used for "video_urls", "video_count", and "webcollage")
        self.video_urls = None
        # whether videos were extracted
        self.extracted_video_urls = False
        # whether product has any videos
        self.has_video = False
        # product json embeded in page html
        self.product_info_json = None

    def _image_count(self):
        """Counts number of (valid) images found
        for this product (not including images saying "no image available")
        Returns:
            int representing number of images
        """

        try:
            images = self._image_urls()
        except Exception:
            images = None
            pass

        if not images:
            return 0
        else:
            return len(images)

    def _image_urls_old(self):
        """Extracts image urls for this product.
        Works on old version of walmart pages.
        Returns:
            list of strings representing image urls
        """

        scripts = self.tree_html.xpath("//script//text()")
        for script in scripts:
            # TODO: is str() below needed?
            #       it sometimes throws an exception for non-ascii text
            try:
                find = re.findall(r'posterImages\.push\(\'(.*)\'\);', str(script))
            except:
                find = []
            if len(find) > 0:
                return self._qualify_image_urls(find)

        if self.tree_html.xpath("//link[@rel='image_src']/@href"):
            if self._no_image(self.tree_html.xpath("//link[@rel='image_src']/@href")[0]):
                return None
            else:
                return self.tree_html.xpath("//link[@rel='image_src']/@href")

        # It should only return this img when there's no img carousel
        pic = [self.tree_html.xpath('//div[@class="LargeItemPhoto215"]/a/@href')[0]]
        if pic:
            # check if it's a "no image" image
            # this may return a decoder not found error
            try:
                if self._no_image(pic[0]):
                    return None
            except Exception, e:
                # TODO: how to get this printed in the logs
                print "WARNING: ", e.message

            return self._qualify_image_urls(pic)
        else:
            return None

    def _qualify_image_urls(self, image_list):
        """Remove no image urls in image list
        """
        qualified_image_list = []

        for image in image_list:
            if not re.match(".*no.image\..*", image):
                qualified_image_list.append(image)

        if len(qualified_image_list) == 0:
            return None
        else:
            return qualified_image_list

    def _is_bundle_product(self):
        if self.tree_html.xpath("//div[@class='js-about-bundle-wrapper']") or \
                        "WalmartMainBody DynamicMode wmBundleItemPage" in html.tostring(self.tree_html):
            return True

        return False

    def _image_urls_new(self):
        """Extracts image urls for this product.
        Works on new version of walmart pages.
        Returns:
            list of strings representing image urls
        """

        if self._version() == "Walmart v2" and self._is_bundle_product():
            return self.tree_html.xpath("//div[contains(@class, 'choice-hero-non-carousel')]//img/@src")
        else:
            def _fix_relative_url(relative_url):
                """Fixes relative image urls by prepending
                the domain. First checks if url is relative
                """

                if not relative_url.startswith("http"):
                    return "http://www.walmart.com" + relative_url
                else:
                    return relative_url

            if not self.product_info_json:
                pinfo_dict = self._extract_product_info_json()
            else:
                pinfo_dict = self.product_info_json

            images_carousel = []

            for item in pinfo_dict['imageAssets']:
                images_carousel.append(item['versions']['hero'])

            if images_carousel:
                # if there's only one image, check to see if it's a "no image"
                if len(images_carousel) == 1:
                    try:
                        if self._no_image(images_carousel[0]):
                            return None
                    except Exception, e:
                        print "WARNING: ", e.message

                return self._qualify_image_urls(images_carousel)

            # It should only return this img when there's no img carousel
            main_image = self.tree_html.xpath("//img[@class='product-image js-product-image js-product-primary-image']/@src")
            if main_image:
                # check if this is a "no image" image
                # this may return a decoder not found error
                try:
                    if self._no_image(main_image[0]):
                        return None
                except Exception, e:
                    print "WARNING: ", e.message

                return self._qualify_image_urls(main_image)

            # bundle product images
            images_bundle = self.tree_html.xpath("//div[contains(@class, 'choice-hero-imagery-components')]//" + \
                                                 "img[contains(@class, 'media-object')]/@src")

            if not images_bundle:
                images_bundle = self.tree_html.xpath("//div[contains(@class, 'non-choice-hero-components')]//" + \
                                                     "img[contains(@class, 'media-object')]/@src")

            if images_bundle:
                # fix relative urls
                images_bundle = map(_fix_relative_url, images_bundle)
                return self._qualify_image_urls(images_bundle)

            # nothing found
            return None

    def _image_urls(self):
        """Extracts image urls for this product.
        Works on both old and new version of walmart pages.
        Returns:
            list of strings representing image urls
        """

        if self._version() == "Walmart v1":
            return self._image_urls_old()

        if self._version() == "Walmart v2":
            return self._image_urls_new()

    def _no_image(self, url):
        """Overwrites the _no_image
        in the base class with an additional test.
        Then calls the base class no_image.

        Returns True if image in url is a "no image"
        image, False if not
        """

        # if image name is "no_image", return True
        if re.match(".*no.image\..*", url):
            return True
        else:
            first_hash = self._image_hash(url)
            if first_hash in self.NO_IMAGE_HASHES:
                print "not an image"
                return True
            else:
                return False

    def _image_hash(self, image_url):
        """Computes hash for an image.
        To be used in _no_image, and for value of _image_hashes
        returned by scraper.
        Returns string representing hash of image.

        :param image_url: url of image to be hashed
        """
        return str(MurmurHash.hash(fetch_bytes(image_url)))

    def load_image_hashes(self):
        '''Read file with image hashes list
        Return list of image hashes found in file
        '''
        path = '../special_crawler/no_img_list.json'
        no_img_list = []
        if os.path.isfile(path):
            f = open(path, 'r')
            s = f.read()
            if len(s) > 1:
                no_img_list = json.loads(s)
            f.close()
        return no_img_list

    def _extract_product_info_json(self):
        """Extracts body of javascript function
        found in a script tag on each product page,
        that contains various usable information about product.
        Stores function body as json decoded dictionary in instance variable.
        Returns:
            function body as dictionary (containing various info on product)
        """
        if self.product_info_json:
            return self.product_info_json

        if self._version() == "Walmart v2" and self._is_bundle_product():
            product_info_json = self._find_between(html.tostring(self.tree_html), 'define("product/data",', ");\n")
            product_info_json = json.loads(product_info_json)
            self.product_info_json = product_info_json

            return self.product_info_json
        else:
            page_raw_text = html.tostring(self.tree_html)
            product_info_json = json.loads(re.search('define\("product\/data",\n(.+?)\n', page_raw_text).group(1))

            self.product_info_json = product_info_json

            return self.product_info_json

    def _video_count(self, video_urls):
        """Whether product has video
        To be replaced with function that actually counts
        number of videos for this product
        Returns:
            1 if product has video
            0 if product doesn't have video
        """

        if not video_urls:
            if self.has_video:
                return 1
            else:
                return 0
        else:
            return len(video_urls)

    def wcobj_shared_code(self, body, video_urls):
        tree = html.fromstring(body)
        wcobj_links = tree.xpath("//img[contains(@class, "
                                     "'wc-media')]/@wcobj")
        if wcobj_links:
            for wcobj_link in wcobj_links:
                if wcobj_link.endswith(".flv"):
                    video_urls.append(wcobj_link)
        return video_urls

    def webcollage_shared_code(self, body, video_urls):
        tree = html.fromstring(body)
        if tree.xpath("//div[@id='iframe-video-content']") and \
                tree.xpath("//table[contains(@class, 'wc-gallery-table')]"
                               "/@data-resources-base"):
            video_base_path = tree.xpath("//table[contains(@class, "
                                             "'wc-gallery-table')]"
                                             "/@data-resources-base")[0]
            sIndex = 0
            eIndex = 0

            while sIndex >= 0:
                sIndex = body.find('{"videos":[', sIndex)
                eIndex = body.find('}]}', sIndex) + 3

                if sIndex < 0:
                    break

                jsonVideo = body[sIndex:eIndex]
                jsonVideo = json.loads(jsonVideo)

                if len(jsonVideo['videos']) > 0:
                    for video_info in jsonVideo['videos']:
                        video_urls.append(video_base_path +
                                               video_info['src']['src'])

                sIndex = eIndex

        return video_urls

    def sellpoints_shared_code(self, body, video_urls):

        video_url_candidates = re.findall("'file': '([^']+)'", body)
        if video_url_candidates:
            for video_url_item in video_url_candidates:
                video_url_candidate = re.sub('\\\\', "", video_url_item)

                # if it ends in flv, it's a video, ok
                if video_url_candidate.endswith(".mp4") or \
                        video_url_candidate.endswith(".flv"):
                        self.has_sellpoints_media = True
                        self.has_video = True
                        video_urls.append(video_url_candidate)
                        break

        return video_urls

    def sellpoints_new_shared_code(self, body, video_urls):
        tree = html.fromstring(body)
        if tree.xpath("//div[@id='iframe-video-content']"
                          "//div[@id='player-holder']"):
            self.has_video = True
            self.has_sellpoints_media = True

        return video_urls

    def last_video_request(self, body, video_urls):
        tree = html.fromstring(body)
        video_json = json.loads(tree.xpath("//div[@class='wc-json-data']/text()")[0])
        video_relative_path = video_json["videos"][0]["sources"][0]["src"]
        video_base_path = tree.xpath("//table[@class='wc-gallery-table']/@data-resources-base")[0]
        video_urls.append(video_base_path + video_relative_path)
        self.has_video = True
        return video_urls

    # check if there is a "Video" button available on the product page
    def _has_video_button(self):
        """Checks if a certain product page has a visible 'Video' button,
        using the page source tree.
        Returns:
            True if video button found (or if video button presence can't be determined)
            False if video button not present
        """

        richMedia_elements = self.tree_html.xpath("//div[@id='richMedia']")
        if richMedia_elements:
            richMedia_element = richMedia_elements[0]
            elements_onclick = richMedia_element.xpath(".//li/@onclick")
            # any of the "onclick" attributes of the richMedia <li> tags contains "video')"
            has_video = any(map(lambda el: "video')" in el, elements_onclick))

            return has_video

        # if no rich media div found, assume a possible error in extraction and return True for further analysis
        # TODO:
        #      return false cause no rich media at all?
        return True

    def _extract_product_id(self):
        """Extracts product id of walmart product from its URL
        Returns:
            string containing only product id
        """
        if self._version() == "Walmart v1":
            product_id = self.product_page_url.split('/')[-1]
            return product_id
        elif self._version() == "Walmart v2":
            product_id = self.product_page_url.split('/')[-1]
            return product_id

        return None

    def _version(self):
        """Determines if walmart page being read (and version of extractor functions
            being used) is old or new design.
        Returns:
            "Walmart v1" for old design
            "Walmart v2" for new design
        """

        # using the "keywords" tag to distinguish between page versions.
        # In old version, it was capitalized, in new version it's not
        if self.tree_html.xpath("//meta[@name='keywords']/@content"):
            return "Walmart v2"
        if self.tree_html.xpath("//meta[@name='Keywords']/@content"):
            return "Walmart v1"

        # we could not decide
        return None
