#!/usr/bin/python

import re
import json
import requests
import traceback

from lxml import html
from urlparse import urljoin
from extract_samsclub_data import SamsclubScraper


class SamsclubShelfScraper(SamsclubScraper):
    ##########################################
    ############### PREP
    ##########################################

    # This must match with _is_shelf_url defined in SamsclubScraper
    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://(www.)samsclub.com/(sams/)(<something>/)<cat-id>.cp' \
                          'or http(s)://(www.)samsclub.com/(sams/)shop/category.jsp?categoryId=<cat-id>' \
                          'or http(s)://(www.)samsclub.com/(sams/)pagedetails/content.jsp?pageName=<page-name>'

    CAT_URL = 'https://www.samsclub.com/sams/redesign/common/model/loadDataModel.jsp?dataModelId={}&dataModelType=category&pageSize=8&offset=1&clubId={}'

    def __init__(self, **kwargs):
        SamsclubScraper.__init__(self, **kwargs)

        self.items_checked = False
        self.items = []

        self.image_urls_checked = False
        self.image_urls = None
        self.image_alts = None

    def check_url_format(self):
        if self._is_shelf_url(self.product_page_url):
            return True

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        self.cat_id = self._cat_id_from_url(self.product_page_url)

        if not self._product_title():
            return True

        return False

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    BODY_COPY_XPATH = '//section[contains(@class,"sc-cat-footer")]/div/*[not(self::style)] | ' \
                      '//section[contains(@class,"sc-cc-seo")]/p/*'

    def _body_copy(self):
        body_copy = self.tree_html.xpath(self.BODY_COPY_XPATH)
        if body_copy:
            body_copy = ''.join([html.tostring(e) for e in body_copy])
            # remove hyperlink info
            return re.sub('<a[^>]*?>([^<]*?)</a>', r'\1', body_copy)

    def _body_copy_links(self):
        if not self._body_copy():
            return None

        return_links = {'self_links': {'count': 0},
                        'broken_links': {'links': {}, 'count': 0}}

        def check_and_add_broken_link(link):
            status_code = requests.head(link, timeout=5).status_code

            if not status_code == 200:
                return_links['broken_links']['links'][link] = status_code
                return_links['broken_links']['count'] += 1

        for link in self.tree_html.xpath(self.BODY_COPY_XPATH + '//a'):
            href = link.xpath('./@href')

            if href:
                href = urljoin(self.product_page_url, href[0])

                cat_id = self._cat_id_from_url(href)

                if cat_id == self.cat_id:
                    return_links['self_links']['count'] += 1

                else:
                    check_and_add_broken_link(href)

            else:
                cat_id = re.match('\d+', cat_id).group()

                if cat_id == self.cat_id:
                    return_links['self_links']['count'] += 1

                else:
                    check_and_add_broken_link('https://www.samsclub.com/sams/{}.cp'.format(cat_id))

        return return_links

    def _meta_description(self):
        # TODO: is this necessary?
        if self.tree_html.xpath('//meta[@name="description"]/@content'):
            return 1
        return 0

    def _meta_description_count(self):
        meta_desc = self.tree_html.xpath('//meta[@name="description"]/@content')

        if meta_desc:
            return len(meta_desc[0])

    # Return an image url with https schema and appropriate size parameters
    def _fix_image_url(self, image_url):
        if image_url:
            image_url = re.sub('\s+', '', image_url)
            image_url = 'https:' + image_url if image_url.startswith('//') else image_url
            return image_url.split('?')[0] + self.IMG_ARGS if 'images.samsclub' in image_url else image_url

    # Return the items displayed on the shelf page (products showing an image and usually price)
    def _items(self):
        if self.items_checked:
            return self.items

        self.items_checked = True

        self.items = []

        subcategories = self.tree_html.xpath('//section[starts-with(@id,"catLowFtrdCrsl")]')

        # If it is a meta-category page
        if subcategories:
            for subcategory in subcategories:
                product_cards = subcategory.xpath('.//div[contains(@class,"sc-product-card")]')

                if not product_cards:
                    cat_id = re.search('_(\d+)$', subcategory.get('ng-controller')).group(1)
                    # Fetch product cards
                    subcategory = html.fromstring(self._request(self.CAT_URL.format(cat_id, self.CLUB_ID)).content)
                    product_cards = subcategory.xpath('.//div[contains(@class,"sc-product-card")]')

                for product_card in product_cards[:5]:
                    image = product_card.xpath('.//img/@src')[0]
                    alt = product_card.xpath('.//img/@alt')[0]
                    price = price = product_card.xpath('.//*/@data-price')[0]
                    if price == 'See price in checkout':
                        price = None
                    else:
                        price = float(price)
                    self.items.append({'image': self._fix_image_url(image), 'alt': alt, 'price': price})

        # Otherwise it is a normal category page
        else:
            items = self.tree_html.xpath('//div[@ng-init]/@ng-init')
            items = [json.loads(re.search('{.*}', i, re.DOTALL).group()) for i in items]

            def image(item):
                return self._fix_image_url(item['listImage'])

            def price(item):
                if item.get('onlinePricing', {}).get('mapOptions') == 'see_price_checkout':
                    return None
                price = item.get('onlinePricing', {}).get('finalPrice', {}).get('currencyAmount')
                return float(price) if price else None

            for item in items:
                self.items.append(
                        {'alt': item['productName'],
                         'image': image(item),
                         'in_stock': item['onlineInventory']['status'] != 'outOfStock',
                         'price': price(item)
                        })

        return self.items

    # Return all images on the shelf page, including item images
    def _image_urls(self):
        if self.image_urls_checked:
            return self.image_urls

        self.image_urls_checked = True

        image_urls = []
        image_alts = []

        try:
            def is_in_featured_categories(element):
                return element.xpath('./ancestor::section[@id="catFeaturedCategories"]')

            featured_images = self.tree_html.xpath('//category-carousel[@carousel-type="featured"]//img')
            featured_images = [fi for fi in featured_images if not is_in_featured_categories(fi)]

            # add the first 3 featured images
            # example: https://www.samsclub.com/sams/specialty-stores/8003.cp?scatId=8003
            if featured_images:
                featured_images = [i for i in featured_images if i.get('src')][:3]
                featured_image_urls = [self._fix_image_url(i.get('src')) for i in featured_images]
                image_urls.extend(featured_image_urls)
                image_alts.extend([i.get('alt') or '' for i in featured_images])

            # only add these other images if there are no featured images
            # example: https://www.samsclub.com/sams/sports-equipment-fitness-equipment/1888.cp
            else:
                other_images = self.tree_html.xpath('//img | //*[starts-with(@style,"background: url(")]')
                other_images = [oi for oi in other_images if not is_in_featured_categories(oi)]

                for image in other_images:
                    # do not include carousel images (that will come later)
                    if image.xpath('./ancestor::div[@class="sc-carousel"]') or \
                            image.xpath('./ancestor::category-carousel'):
                        continue

                    image_url = image.get('src')
                    if not image_url and image.get('style'):
                        image_url = re.match('background: url\((.*?)\)', image.get('style')).group(1)
                    image_url = self._fix_image_url(image_url)

                    if image_url and image_url not in image_urls and \
                            not image_url.endswith('.png') and not image_url.endswith('.gif'):
                        image_urls.append(image_url)
                        image_alts.append(image.get('alt') or '')

            # add the item images
            for item in self._items():
                if item['alt'] not in image_alts:
                    image_urls.append(item['image'])
                    image_alts.append(item['alt'])

            carousels = self.tree_html.xpath('//div[@class="sc-carousel"] | '
                                             '//category-carousel[not(@carousel-type="featured")]')
            carousels = [c for c in carousels if not is_in_featured_categories(c)]

            # add the first 5 images from each carousel
            for carousel in carousels:
                for image in carousel.xpath('.//img')[:5]:
                    image_url = self._fix_image_url(image.get('src'))
                    if image_url and not image_url in image_urls:
                        image_urls.append(image_url)
                        image_alts.append(image.get('alt') or '')

            if image_urls:
                self.image_urls = image_urls
                self.image_alts = image_alts
                return self.image_urls

        except:
            print traceback.format_exc()

    def _image_alt_text(self):
        self._image_urls()
        return self.image_alts

    def _item_prices(self):
        return [i['price'] for i in self._items() if i['price']]

    def _lowest_item_price(self):
        if self._item_prices():
            return min(self._item_prices())

    def _highest_item_price(self):
        if self._item_prices():
            return max(self._item_prices())

    def _num_items_price_displayed(self):
        return len(self._item_prices())

    def _num_items_no_price_displayed(self):
        return self._results_per_page() - self._num_items_price_displayed()

    def _results_per_page(self):
        return len(self._items())

    def _total_matches(self):
        search_info = re.search('var searchInfo = ({.*?});', self.page_raw_text, re.DOTALL)
        if search_info:
            search_info = re.sub('\'', '"', re.sub('"', '\\"', search_info.group(1)))
            search_info = json.loads(search_info)
            return int(search_info['totalRecords'])

    def _product_name(self):
        return self.tree_html.xpath('//h1/text()')[0]

    def _in_stock(self):
        return 1 if self._items() else 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = re.search('googleAddBreadCrumbLinkText=\'(.*?)\'', self.page_raw_text)
        if categories:
            categories = categories.group(1).split('/')[1:-1]
            if categories:
                return [c.replace('_', ' ') for c in categories]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : PRODUCT_INFO
        "image_urls": _image_urls,
        "image_alt_text": _image_alt_text,
        "product_name": _product_name,
        "in_stock": _in_stock,

        # CONTAINER : PAGE_ATTRIBUTES
        "meta_description": _meta_description,
        "meta_description_count": _meta_description_count,
        "results_per_page": _results_per_page,
        "total_matches": _total_matches,
        "lowest_item_price": _lowest_item_price,
        "highest_item_price": _highest_item_price,
        "num_items_price_displayed": _num_items_price_displayed,
        "num_items_no_price_displayed": _num_items_no_price_displayed,
        "body_copy": _body_copy,
        "body_copy_links": _body_copy_links,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        }
