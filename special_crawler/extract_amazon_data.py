# -*- coding: utf-8 -*-
# !/usr/bin/python

import re
import json
import time
import urllib
import requests
import urlparse
import traceback
from lxml import html
from HTMLParser import HTMLParser

import spiders_shared_code.canonicalize_url

from extract_data import Scraper, cached
from captcha_solver import CaptchaBreakerWrapper
from spiders_shared_code.amazon_variants import AmazonVariants
from product_ranking.guess_brand import guess_brand_from_first_words


class AmazonScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    CAPTCHA_URL = '/errors/validateCaptcha?amzn={0}&amzn-r={1}&field-keywords={2}'

    CW = CaptchaBreakerWrapper()

    ADDRESS_CHANGE = '/gp/delivery/ajax/address-change.html'

    BUSINESS_HEADERS = {
        'Cookie': 'skin=noskin; a-ogbcbff=1; session-token="+NBZPwQvaHQbhK5vUjRvLZ0ov9zCbWUxy5ATIcrszHOjUNecwj8CeJm+Rr7WoeXOAo213vXutmcJBzRqRaONkx9UIPOJuBkZR4/ZGzJHMCSMOeli9q+QhN4YKYkQFumVzy5ZHPbmOmj8cT2Hbt66y4c+OwTSI1Dv1fqEql+UUq4hLL9K2gaKOlM45lNtRGQX/kI6Y1i1HymY9x8XLrE2uyN0EaKbBR9LdmlCkHYtMwWXjG6CVEvi0zS8o5lQs+dKpzaXLuTIbPdAK1OdE3OrZg=="; x-main="YFw6smIx@dGM1MHOaZLrgOtk2foUUwMWvsCPIoZFUAi6fClRmJDNqEf07qDS1qkD"; at-main=Atza|IwEBINw0cKgo8MSwPnW9gCaS7txlIOhvD-6Gr1fE_N36qLXbL0VGgTQxj4efVTn3Z2mkgW_ME8Kkp2-8KbCxgURTab1OfBZtZ4QLXdDU5Rn59Z1y5G4waf1LQZoxfoQDRVQAtUStQhK0_wl2IjQNS3RBZfF4YuMuCatDdqD7hvM2vK5Dr7DmXWF5XDYKtzQB-WeOTX92TPz4eIimILLm4G0GIvRQhuum6Hy6m586xVoKUcDPmSDcc9e2pZnRJuDqGIzAKNNRABKkM3bZkEVuysHBMSpDSgi9wXw8McjKm4zIKj10q7UfgZKRHSfp9fQJCNU2NoxCuVoog7gEIEwtaYDc7PrW1nMzzOPfgXrXZN1b6sR7kUtBef3aWa1AeRjxzvB-vR-aX2okf5nz6O1kZgr_n8H4; sess-at-main="A9FKPpUPmBiOroGVPzvjPjeSBx/CNjUD1HoSbLUR/v0="; lc-main=en_US; x-wl-uid=1GmrL/1glNojZktMekSexUEz+54hj8e85AhjUXArXmwX4UMaeQzlVtabiNifpuG1kdcdfMWF6GxjA7Ns++bZphJYEEUQgdcwGkHJl8E3c1yU7s/IuIAqcmK+8VAKoPuB82cil3czpYrU=; csm-hit=%7B%22tb%22%3A%22ESC1DGCVQ78Z7JATYTPQ%2Bs-CVS3R78H09E93QJBTXMW%7C1510704359433%22%2C%22adb%22%3A%22adblk_yes%22%7D; ubid-main=134-6888992-1229153; session-id-time=2082787201l; session-id=137-6609697-2927617'
    }

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(www.|primenow.)amazon.(com.mx|co.uk|com|ca|cn|de|in|fr|es)/dp/<product-id>"

    PRIME_HOME = '/onboard?sourceUrl=%2F'

    PRIME_LOG_IN = '/cart/initiatePostalCodeUpdate?newPostalCode=' \
                   '{postalCode}&noCartUpdateRequiredUrl=%2F&allCartItemsSwappableUrl' \
                   '=%2F&someCartItemsUnswappableUrl=%2F&offer-swapping-token' \
                   '={csrf_token}'

    REVIEW_RETRIES = 3

    REVIEW_URL = "/product-reviews/{}/ref=cm_cr_arp_d_viewopt_rvwer?reviewerType=all_reviews&filterByStar={}_star"


    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.zip_code = kwargs.get('zip_code', '94102')

        self.av = AmazonVariants()
        self.is_review_checked = False
        self.review_list = None
        self.is_marketplace_sellers_checked = False
        self.marketplace_prices = None
        self.marketplace_sellers = None
        self.is_variants_checked = False
        self.variants = None
        self.image_names = []
        self.no_image_available = 0
        self.temp_price_cut = 0
        self.ingredients = None

        # alternate info
        self.alt_product_name = None
        self.alt_description = None
        self.alt_long_description = None
        self.alt_features = None

        self.image_urls_checked = False
        self.image_urls = None

        self.proxies_enabled = False  # first, they are OFF to save allowed requests

        # request https instead of http
        self.product_page_url = re.sub('http://', 'https://', self.product_page_url)

        self.is_prime = False

        # add fragment to get full specs (CON-25063)
        if not re.search('showDetailTechData=1', self.product_page_url):
            if '?' in self.product_page_url:
                self.product_page_url = self.product_page_url + '&showDetailTechData=1'
            else:
                self.product_page_url = self.product_page_url + '?showDetailTechData=1'

        self.session = requests.Session()

    def _request(self, url, data=None, verb='get', session=None, timeout=None, log_status_code=False):
        return super(AmazonScraper, self)._request(url,
                                                   data=data,
                                                   verb=verb,
                                                   session=session,
                                                   timeout=timeout,
                                                   use_proxies=bool(re.search('amazon.(com|ca|co|fr)', url)),
                                                   allow_redirects=False,
                                                   # do not allow redirects so that is_redirect is logged
                                                   log_status_code=log_status_code,
                                                   )

    def _request_fresh_page(self):
        self._request(self.product_page_url, session=self.session)

        self._request(urlparse.urljoin(self.product_page_url, self.ADDRESS_CHANGE),
                      data = {'locationType': 'LOCATION_INPUT', 'zipCode': self.zip_code},
                      session=self.session,
                      verb='post')

        return self._request(self.product_page_url, session=self.session, log_status_code=True)

    def _request_prime_page(self):
        welcome_response = self._request(urlparse.urljoin(self.product_page_url, self.PRIME_HOME),
                                         session=self.session)

        home_html = welcome_response.content
        csrf_token = html.fromstring(home_html).xpath(
            "//form[@id='locationSelectForm']"
            "//input[@name='offer-swapping-token']"
            "/@value")
        if csrf_token:
            csrf_token = csrf_token[0]
        else:
            csrf_token = re.search('"offerSwappingToken":(.*?),', home_html)
            if csrf_token:
                csrf_token = csrf_token.group(1).replace('\"', '').strip()

        self._request(
            urlparse.urljoin(self.product_page_url, self.PRIME_LOG_IN).format(
                postalCode=self.zip_code,
                csrf_token=str(csrf_token)
            ),
            session=self.session
        )

        return self._request(self.product_page_url, session=self.session, log_status_code=True)

    @cached
    def _extract_page_tree(self):
        for i in range(10):

            # if we have already tried a few times, set proxies
            if i >= 3:
                self._set_proxy()

            # Reset error fields

            self.is_timeout = False

            self.ERROR_RESPONSE['failure_type'] = None

            if self.lh:
                self.lh.add_log('status_code', None)

            try:
                if self.is_prime:
                    resp = self._request_prime_page()
                elif 'ppw=fresh' in self.product_page_url.lower():
                    self.HEADERS = self.BUSINESS_HEADERS
                    resp = self._request_fresh_page()
                else:
                    if 'business=true' in self.product_page_url.lower():
                        self.HEADERS = self.BUSINESS_HEADERS
                    resp = self._request(self.product_page_url, session=self.session, log_status_code=True)

                if resp.status_code != 200:
                    # consider non-200 status codes as failure
                    self.is_timeout = True
                    self.ERROR_RESPONSE['failure_type'] = resp.status_code

                    # do not retry these status codes
                    if resp.status_code in [404, 429]:
                        return

                    # use port 60000 for status code 503 (CON-39598)
                    elif resp.status_code == 503:
                        self._set_proxy(to='proxy_out.contentanalyticsinc.com:60000')

                # if there was an error, retry
                if self.is_timeout:
                    continue

                # otherwise, extract the page tree
                try:
                    contents = self._clean_null(resp.text)
                    self.tree_html = html.fromstring(contents.decode("utf8"))
                except UnicodeError, e:
                    print "Warning creating html tree from page content: ", e.message

                    contents = self._clean_null(resp.text)
                    self.tree_html = html.fromstring(contents)

                captcha_form = self.tree_html.xpath("//form[contains(@action,'Captcha')]")

                # if there is a captcha, try solving it
                if captcha_form:
                    is_captcha = True
                    self.is_timeout = True
                    self.ERROR_RESPONSE['failure_type'] = 'CAPTCHA'

                    captcha_img = captcha_form[0].xpath('.//img/@src')[0]
                    captcha_text = self.CW.solve_captcha(captcha_img)

                    amzn = self.tree_html.xpath('//input[@name="amzn"]/@value')[0]
                    amzn_r = self.tree_html.xpath('//input[@name="amzn-r"]/@value')[0]

                    captcha_url = urlparse.urljoin(self.product_page_url,
                            self.CAPTCHA_URL.format(urllib.quote(amzn), urllib.quote(amzn_r), captcha_text))

                    self._request(captcha_url, session=self.session)

                    continue

                # if it is a prime pantry page, re-request with business headers
                if self._pantry() and not hasattr(self, 'HEADERS'):
                    self.HEADERS = self.BUSINESS_HEADERS
                    continue

                # if nothing is wrong, return
                return

            except requests.exceptions.ProxyError, e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', 'Proxy Error: {}'.format(e))

                self.is_timeout = True
                self.ERROR_RESPONSE['failure_type'] = 'proxy'
                return

            except requests.exceptions.ConnectionError, e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', 'Connection Error: {}'.format(e))

                if 'Max retries exceeded' in str(e):
                    self.is_timeout = True
                    self.ERROR_RESPONSE['failure_type'] = 'max_retries'
                    return

                self.is_timeout = True
                self.ERROR_RESPONSE['failure_type'] = str(e)

            except Exception, e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', 'Error extracting page tree: {}'.format(e))

                self.is_timeout = True
                self.ERROR_RESPONSE['failure_type'] = str(e)

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.amazon(url)

    def check_url_format(self):
        parse_result = urlparse.urlparse(self.product_page_url)

        m = re.search('amazon\.(com\.mx|co\.uk|com|ca|cn|de|in|fr|es)$', parse_result.netloc)
        if m:
            self.scraper_version = m.group(1).split('.')[-1]

            m = re.search('/([A-Za-z\d]{10})(?:/|$)', parse_result.path)
            if m:
                self.product_id = m.group(1)

                if 'primenow' in self.product_page_url:
                    self.is_prime = True
                    self.zip_code = '10036'

                if self.scraper_version == 'uk':
                    self.zip_code = 'EC2R 6AB'

                return True

    def not_a_product(self):
        self.av.setupCH(self.tree_html, self.product_page_url)

        self._get_alternate_info()

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        if self.product_id:
            return self.product_id

        for frag in reversed(self.product_page_url.split('?')[0].split('/')):
            if frag and re.match('^[\w\d]+$', frag):
                return frag

    ##########################################
    ################ CONTAINER : PRODUCT_INFO
    ##########################################

    def _get_alternate_info(self):
        try:
            alt = re.search('immutableURLPrefix":"([^"]+)"', html.tostring(self.tree_html)).group(1)
            alt = urlparse.urljoin(self.product_page_url, alt)

            for variant in self._variants():
                if variant['asin'] == self._asin():
                    variant_alt = alt + '&asinList={0}&id={0}'.format(variant['asin'])
                    alternate_info = self._request(variant_alt).content
                    alternate_info = re.sub('\\\\.', '', re.sub('\\\\/', '/', re.sub('\\\\"', '"', re.sub('\s+', ' ', alternate_info))))
                    self.alt_product_name = re.search('<span id="productTitle"[^>]*>([^<]+)<', alternate_info).group(1)
                    self.alt_description = re.search('"featurebullets_feature_div":"([^}]+)"}', alternate_info).group(1)
                    self.alt_features = re.search('<table id="productDetails_detailBullets.*?</table>',
                                                  alternate_info).group()
                    # nested product description based on https://www.amazon.com.mx/dp/B004YK2KSM (CON-36576)
                    nested_product_description = re.search('<div id="productDescription.*?<p>\s*(<p>.*?</p>)',
                                                           alternate_info)
                    if nested_product_description:
                        self.alt_long_description = nested_product_description.group(1)
                    else:
                        self.alt_long_description = re.search('<div id="productDescription.*?(<p>.*?</p>)',
                                                              alternate_info).group(1)
        except:
            pass

    def _product_name(self):
        if self.alt_product_name:
            return self.alt_product_name.strip()

        pn = self.tree_html.xpath('//h1[@id="title"]/span[@id="productTitle"]')
        if len(pn) > 0:
            return self._clean_text(pn[0].text)
        pn = self.tree_html.xpath(
            '//h1[@class="parseasinTitle " or @class="parseasinTitle"]/span[@id="btAsinTitle"]//text()')
        if len(pn) > 0:
            return self._clean_text(" ".join(pn).strip())
        pn = self.tree_html.xpath('//h1[@id="aiv-content-title"]//text()')
        if len(pn) > 0:
            return self._clean_text(pn[0])
        pn = self.tree_html.xpath('//div[@id="title_feature_div"]/h1//text()')
        if len(pn) > 0:
            return self._clean_text(pn[0].strip())
        pn = self.tree_html.xpath('//span[@id="ebooksProductTitle"]/text()')
        if len(pn) > 0:
            return self._clean_text(pn[0].strip())
        pn = self.tree_html.xpath('//div[@id="item_name"]/text()')
        return self._clean_text(pn[0].strip())

    def _model(self):
        textVariants = {
            'cn': u'\u578b\u53f7',
            'de': 'Modellnummer',
            'fr': u'Num\u00e9ro du mod\u00e8le',
            'es': u'N\u00FAmero de modelo del producto',
            'mx': u'N\u00FAmero de modelo del producto'
        }
        searchText = textVariants.get(self.scraper_version, 'Item model number')
        model = self.tree_html.xpath(u'//*[contains(text(), "{}")]//following-sibling::td/text()'.format(searchText))
        if not model:
            model = self.tree_html.xpath(u'//b[contains(text(), "{}")]//parent::li/text()'.format(searchText))
        if not model:
            model = self.tree_html.xpath(u'//tr[contains(th/text(), "Model number")]/td/text()')
        if model:
            return model[0].strip()

    def _upc(self):
        upc = re.search('UPC:</b> (\d+)', html.tostring(self.tree_html))
        if upc:
            return upc.group(1)

        upc = self.tree_html.xpath('//th[contains(text(), "UPC")]//following-sibling::td/text()')
        if upc:
            return upc[0].split(',')[0].strip()

        for key, value in (self._specs() or {}).items():
            if key == 'UPC':
                return value

    # Amazon's version of UPC
    def _asin(self):
        return self._product_id()

    def _specs(self):
        specs = {}

        for r in self.tree_html.xpath('//table[@id="productDetails_techSpec_section_1"]/tr'):
            key = r.xpath('./th/text()')[0].strip()
            value = r.xpath('./td/text()')[0].strip()

            specs[key] = value

        if not specs:
            for r in self.tree_html.xpath('//div[@id="technicalProductFeatures"]/following-sibling::div/ul/li'):
                key = r.xpath('./b/text()')[0]
                value = r.text_content().split(': ')[-1]

                specs[key] = value

        if not specs:
            for r in self.tree_html.xpath('//div[@class="section techD" and .//span[contains(text(), "technique")'
                                          ' or contains(text(), "Technical")]]//tr'):
                key = r.xpath('./td[@class="label"]/text()')
                value = r.xpath('./td[@class="value"]')
                if key and value and key[0].strip() != '' and value[0].text_content().strip() != '':
                    specs[key[0].strip()] = value[0].text_content().strip()

        if specs:
            return specs

    def _features(self):
        if self.alt_features:
            features = self.alt_features.decode('utf-8')
            features = self._remove_tags(self._clean_text(self._exclude_javascript_from_description(features)))
            features = re.sub('<script>.*?<script>', '', re.sub('<style>.*?<style>', '', features))
            features = re.sub('<td>\s*<tr>', '</td></tr>', features)
            feature_info = [html.fromstring(features)]
        else:
            feature_info = self.tree_html.xpath("//table[@id='productDetails_detailBullets_sections1']")

        features = []

        if feature_info:
            rows = feature_info[0].xpath(".//tr")

            for row in rows:
                head = row.xpath(".//th/text()")
                value = row.xpath(".//td")

                if head and value:
                    head = head[0].strip()

                    if 'reviews' in head.lower():
                        values = value[0].xpath("./text()")
                    else:
                        values = value[0].text_content().split('\n')

                    values = filter(None, [self._clean_text(v) for v in values])
                    value = '\n'.join(values)
                    features.append(head + ': ' + value)

        else:
            feature_info = self.tree_html.xpath(
                "//div[contains(@id, 'detail-bullets')or contains(@id, 'detail_bullets')]//ul"
            )

            if feature_info:
                rows = feature_info[0].xpath(".//li")

                for row in rows:
                    head = row.xpath(".//b/text()")
                    value = row.xpath("./text()")

                    if head and value:
                        features.append(head[0].strip() + value[0].strip())

        return features if features else None

    def _remove_tags(self, description):
        # remove attributes
        description = re.sub('(<\w+)[^>]*?(/?>)', r'\1\2', description)
        # remove div and span tags
        description = re.sub('</?div>|</?span>', '', description)
        return description.strip()

    def _description(self):
        if self.alt_description:
            description = [html.fromstring(self.alt_description)]
        else:
            description = self.tree_html.xpath("//*[contains(@id,'feature-bullets')]")

        if description:
            description = description[0]

            hidden = description.xpath('//*[@class="aok-hidden"]')
            more_button = description.xpath('//div[@id="fbExpanderMoreButtonSection"]')
            expander = description.xpath(".//*[contains(@class, 'a-expander-extend-header')]")

            more_links = description.xpath('.//*[@id="seeMoreDetailsLink"]')

            # remove expander(=show mores) from description
            if expander:
                expander[0].getparent().remove(expander[0])

            description = html.tostring(description)

            if more_links:
                description = re.sub(html.tostring(more_links[0]), '', description)

            for exclude in hidden + more_button:
                description = re.sub(html.tostring(exclude), '', description)

            return self._remove_tags(self._clean_text(self._exclude_javascript_from_description(description)))

        short_description = " ".join(
            self.tree_html.xpath("//div[@class='dv-simple-synopsis dv-extender']//text()")).strip()

        if short_description:
            return self._remove_tags(self._exclude_javascript_from_description(short_description.replace("\n", " ")))

        return self._long_description_helper()

    def clean_bullet_html(self, el):
        l = el.xpath(".//text()")
        l = " ".join(l)
        l = " ".join(l.split())
        return l

    def _bullets(self):
        bullets = self.tree_html.xpath("//*[contains(@id,'feature-bullets')]//ul/li[not(contains(@class,'hidden'))]")
        bullets = [b.xpath("*//text()") for b in bullets]
        bullets = filter(None, [self._clean_text(b[0]) for b in bullets if b])
        if bullets:
            return '\n'.join(bullets)

    def _seller_ranking(self):
        seller_ranking = []

        if self.tree_html.xpath("//li[@id='SalesRank']"):
            ranking_info = self.tree_html.xpath("//li[@id='SalesRank']/text()")[1].strip()

            if ranking_info:
                seller_ranking.append(
                    {"category": ranking_info[ranking_info.find(" in ") + 4:ranking_info.find("(")].strip(),
                     "ranking": int(ranking_info[1:ranking_info.find(" ")].strip().replace(",", ""))})

            ranking_info_list = [item.text_content().strip() for item in
                                 self.tree_html.xpath("//li[@id='SalesRank']/ul[@class='zg_hrsr']/li")]

            for ranking_info in ranking_info_list:
                seller_ranking.append({"category": ranking_info[ranking_info.find("in") + 2:].strip(),
                                       "ranking": int(ranking_info[1:ranking_info.find(" ")].replace(",", "").strip())})
        else:
            ranking_info_list = self.tree_html.xpath(
                "//td[preceding-sibling::th/@class='a-color-secondary a-size-base prodDetSectionEntry' and contains(preceding-sibling::th/text(), 'Best Sellers Rank')]/span/span")
            ranking_info_list = [ranking_info.text_content().strip() for ranking_info in ranking_info_list]

            for ranking_info in ranking_info_list:
                seller_ranking.append(
                    {"category": ranking_info[ranking_info.find("in") + 2:ranking_info.find("(See Top ")].strip(),
                     "ranking": int(ranking_info[1:ranking_info.find(" ")].replace(",", "").strip())})

        if seller_ranking:
            return seller_ranking

    def _long_description(self):
        d1 = self._description()
        d2 = self._long_description_helper()

        # Don't include webcollage content (CON-37412)
        if not d2 or 'class="aplus' in d2:
            return None

        if d1 != d2:
            desc_html = html.fromstring(d2)
            more_links = desc_html.xpath(".//a[contains(text(), 'See all')]")
            if more_links:
                desc_html.remove(more_links[0])
                d2 = html.tostring(desc_html)

            return d2

    def _exclude_images_from_description(self, block):
        all_items_list = block.xpath(".//*")
        remove_candidates = []

        for item in all_items_list:
            if item.tag == "img":
                remove_candidates.append(item)

            if item.xpath("./@style") and (
                    'border-top' in item.xpath("./@style")[0] or 'border-bottom' in item.xpath("./@style")[0]):
                remove_candidates.append(item)

        for item in remove_candidates:
            item.getparent().remove(item)

    def _long_description_helper(self):
        if self.alt_long_description:
            return self.alt_long_description

        try:
            description = ""
            block = self.tree_html.xpath('//*[@class="productDescriptionWrapper"]')[0]

            for item in block:
                description = description + html.tostring(item)

            description = self._clean_text(self._exclude_javascript_from_description(description))

            if description is not None and len(description) > 5:
                return description
        except:
            pass

        try:
            description = ""
            block = self.tree_html.xpath('//div[@id="psPlaceHolder"]/preceding-sibling::noscript')[0]

            for item in block:
                description = description + html.tostring(item)

            description = self._clean_text(self._exclude_javascript_from_description(description))

            if description is not None and len(description) > 5:
                return description
        except:
            pass

        try:
            description = ""
            children = self.tree_html.xpath(
                "//div[@id='productDescription']/child::*[not(@class='disclaim') and not(name()='script') and not(name()='style')]")
            header = False

            for child in children:
                if header and child.text_content():
                    if header == 'ingredients':
                        self.ingredients = child.text_content()
                    header = None
                    continue

                self._exclude_images_from_description(child)

                if 'Product Description' in html.tostring(child):
                    continue

                if child.tag == 'h3':
                    header = child.text.lower().strip()
                    if header in ['from the manufacturer', 'ingredients', 'amazon.com']:
                        continue
                    else:
                        header = None

                if not 'class="aplus"' in html.tostring(child):
                    description += self._clean_text(self._exclude_javascript_from_description(html.tostring(child)))

            if description is not None and len(description) > 5:
                return description
        except:
            pass

        try:
            description = ""
            block = self.tree_html.xpath("//h2[contains(text(),'Product Description')]/following-sibling::*")[0]

            all_items_list = block.xpath(".//*")
            remove_candidates = []

            for item in all_items_list:
                if item.tag == "img":
                    remove_candidates.append(item)

                if item.xpath("./@style") and (
                        'border-top' in item.xpath("./@style")[0] or 'border-bottom' in item.xpath("./@style")[0]):
                    remove_candidates.append(item)

            for item in remove_candidates:
                item.getparent().remove(item)

            for item in block:
                description = description + html.tostring(item)

            description = self._clean_text(self._exclude_javascript_from_description(description))

            if description is not None and len(description) > 5:
                return description
        except:
            pass

        try:
            description = '\n'.join(self.tree_html.xpath('//script//text()'))
            description = re.findall(r'var iframeContent = "(.*)";', description)
            description = urllib.unquote_plus(str(description))
            description = html.fromstring(description)
            description = description.xpath('//div[@class="productDescriptionWrapper"]')
            res = ""
            for d in description:
                if len(d.xpath('.//div[@class="aplus"]')) == 0:
                    res += self._clean_text(' '.join(d.xpath('.//text()'))) + " "
            if res != "":
                return res
        except:
            pass

    def _apluscontent_desc(self):
        res = self._clean_text(' '.join(self.tree_html.xpath('//div[@id="aplusProductDescription"]//text()')))
        if res != "": return res
        desc = '\n'.join(self.tree_html.xpath('//script//text()'))
        desc = re.findall(r'var iframeContent = "(.*)";', desc)
        desc = urllib.unquote_plus(str(desc))
        desc = html.fromstring(desc)
        res = self._clean_text(' '.join(desc.xpath('//div[@id="aplusProductDescription"]//text()')))
        if res != "": return res
        res = self._clean_text(
            ' '.join(desc.xpath('//div[@class="productDescriptionWrapper"]/div[@class="aplus"]//text()')))
        if res != "": return res

    def _get_variant_images(self):
        result = []
        for img in self.tree_html.xpath('//*[contains(@id, "altImages")]'
                                        '//img[contains(@src, "/")]/@src'):
            result.append(re.sub(r'\._[A-Z\d,_]{1,50}_\.jpg', '.jpg', img))
        return result

    def _variants(self):
        if self.is_variants_checked:
            return self.variants

        self.is_variants_checked = True

        self.variants = self.av._variants()

        if self.variants:
            # find default ("selected") variant and insert its images
            for variant in self.variants:
                if variant.get('selected', None):
                    variant['associated_images'] = self._get_variant_images()
        if not self.variants:
            self.variants = self.av._variants_format()

        return self.variants

    def _swatches(self):
        return self.av._swatches()

    def _ingredients(self):
        page_raw_text = html.tostring(self.tree_html)

        try:
            ingredients = re.search('<b>Ingredients</b><br>(.+?)<br>', page_raw_text).group(1)
            r = re.compile(r'(?:[^,(]|\([^)]*\))+')
            ingredients = r.findall(ingredients)
            ingredients = [ingredient.strip() for ingredient in ingredients]

            if ingredients:
                return ingredients
        except:
            pass

        try:
            desc = '\n'.join(self.tree_html.xpath('//script//text()'))
            desc = re.findall(r'var iframeContent = "(.*)";', desc)
            desc = urllib.unquote_plus(str(desc))
            ingredients = re.search('Ingredients:(.+?)(\\n|\.)', desc).group(1)

            if "</h5>" in ingredients:
                return None

            r = re.compile(r'(?:[^,(]|\([^)]*\))+')
            ingredients = r.findall(ingredients)

            ingredients = [ingredient.strip() for ingredient in ingredients]

            if ingredients:
                return ingredients
        except:
            pass

        try:
            start_index = page_raw_text.find('<span class="a-text-bold">Ingredients</span>')

            if start_index < 0:
                raise Exception("Ingredients doesn't exist!")

            start_index = page_raw_text.find('<p>', start_index)
            end_index = page_raw_text.find('</p>', start_index)
            ingredients = page_raw_text[start_index + 3:end_index]
            r = re.compile(r'(?:[^,(]|\([^)]*\))+')
            ingredients = r.findall(ingredients)
            ingredients = [ingredient.strip() for ingredient in ingredients]

            if ingredients:
                return ingredients
        except:
            pass

        if self.ingredients:
            return [i.strip() for i in self.ingredients.split(',')]

        amazon_ingredients = self._amazon_ingredients()
        if amazon_ingredients:
            return [i.strip() for i in self._amazon_ingredients().split(',')]

        xpathes = "//div[@id='productDescription']" \
                  "//h3[text()='Product Description']/following-sibling::p/text() | " \
                  "//div[@id='productDescription']//p/text()"

        description = self.tree_html.xpath(xpathes)

        try:
            desc_ingredients = re.search(r'Ingredients:(.*)(.)?', description[0]).group(1)
            if u'\u2022' in desc_ingredients:
                return [i.strip() for i in desc_ingredients.split(u'\u2022')]
            if ',' in desc_ingredients:
                return [i.strip() for i in desc_ingredients.split(',')]
        except:
            pass

        special_ingredients = self.tree_html.xpath(
            "//div[@class='aplus-module-wrapper']"
            "//h3[contains(@class, 'a-spacing-small') and contains(text(), 'Ingredients')]"
            "/following-sibling::div[@class='a-spacing-extra-large']"
            "//table//td[@class='apm-top']//h4[@class='a-spacing-mini']/text()"
        )

        if special_ingredients:
            return [i.strip() for i in special_ingredients]

    def _nutrition_facts(self):
        page_raw_text = html.tostring(self.tree_html)
        page_raw_text = urllib.unquote_plus(page_raw_text)
        nutrition_facts = None
        nutrition_labels = None
        nutrition_values = None
        try:
            start_index = page_raw_text.find('<h5>Nutritional Facts and Ingredients:</h5>')

            if start_index > 0:
                start_index = page_raw_text.find('<p>', start_index)
                end_index = page_raw_text.find('</p>', start_index)

                nutrition_facts = page_raw_text[start_index + 3:end_index]
                r = re.compile(r'(?:[^,(]|\([^)]*\))+')
                nutrition_facts = r.findall(nutrition_facts)
                nutrition_facts = [nutrition_fact.strip() for nutrition_fact in nutrition_facts]
            else:
                tables = self.tree_html.xpath("//div[contains(@class, 'pdSection')]//strong/text()")
                for t in tables:
                    if 'nutrition facts' in t.lower():
                        index = tables.index(t)
                        nutrition_labels = self.tree_html.xpath("//div[@class='pdTab']")[index].xpath(
                            ".//td[@class='label']/text()")
                        nutrition_values = self.tree_html.xpath("//div[@class='pdTab']")[index].xpath(
                            ".//td[@class='value']/text()")
                if nutrition_labels and nutrition_values:
                    nutrition_facts = [label + ': ' + nutrition_values[nutrition_labels.index(label)] for label in nutrition_labels]
            if nutrition_facts:
                return nutrition_facts
        except:
            print traceback.format_exc()

    def _no_longer_available(self):
        for xpath in ('//div[contains(@id, "availability")]//text()',
                '//div[contains(@id, "outOfStock")]//text()',
                '//div[@id="buyBoxContent"]//text()'):
            for phrase in ('currently unavailable',
                    'no disponible por el momento',
                    'sign up to be notified when this item becomes available',
                    'no disponible'):
                if phrase in ' '.join(self.tree_html.xpath(xpath)).lower():
                    return 1
        return 0

    def _important_information_helper(self, name):
        important_information = self.tree_html.xpath('//div[@id="importantInformation"]/div/div')

        if important_information:
            important_information = html.tostring(important_information[0])

            tags = ['<b>', '<h5>']
            tail_tags = ['</b>', '</h5>']
            idx = 0
            for t in tags:
                name_index = important_information.find(t + name)

                if name_index == -1:
                    idx += 1
                    continue

                start_index = important_information.find(tail_tags[idx], name_index) + len(tail_tags[idx])

                # end at the next bold element
                end_index = important_information.find(t, start_index + 1)

                if end_index == -1:
                    end_index = important_information.find('</div>', start_index + 1)

                important_information = important_information[start_index: end_index].strip()
                # remove extra <br>s at the end
                return re.sub('(<br>)*$', '', important_information)

        x = '//div[@id="important-information"]//span[text()="{0}"]/parent::div/p/text()'.format(name)
        found = self.tree_html.xpath(x)
        if found:
            return found[0]

    def _amazon_ingredients(self):
        return self._important_information_helper('Ingredients')

    def _usage(self):
        return self._important_information_helper('Usage')

    def _directions(self):
        return self._important_information_helper('Directions')

    def _warnings(self):
        warnings = self.tree_html.xpath("//tr[@class='allergenInformation']//td[@class='value']/text()")
        if not warnings:
            return self._important_information_helper('Safety')
        return warnings[0]

    def _indications(self):
        return self._important_information_helper('Indications')

    def _has_warning(self):
        return 1 if self.tree_html.xpath('//div[@id="cpsia-product-safety-warning_feature_div"]') else 0
 
    def _warning_text(self):
        if self._has_warning():
            warnings = self.tree_html.xpath('//div[@class="cpsiaWarning"]')[1:]
            return '\n'.join([w.text_content() for w in warnings])

    ##########################################
    ################ CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]
        return urlparse.urljoin(self.product_page_url, canonical_link)

    def _get_origin_image_urls_from_thumbnail_urls(self, thumbnail_urls):
        origin_image_urls = []

        for url in thumbnail_urls:
            if url == u'http://ecx.images-amazon.com/images/I/31138xDam%2BL.jpg':
                continue

            if "PKmb-play-button-overlay-thumb_.png" in url:
                continue

            image_file_name = url.split("/")[-1]
            offset_index_1 = image_file_name.find(".")
            offset_index_2 = image_file_name.rfind(".")

            if offset_index_1 == offset_index_2:
                if not url in origin_image_urls:
                    origin_image_urls.append(url)
            else:
                image_file_name = image_file_name[:offset_index_1] + image_file_name[offset_index_2:]
                url = url[:url.rfind("/")] + "/" + image_file_name
                if not url in origin_image_urls:
                    origin_image_urls.append(url)

        if origin_image_urls:
            return origin_image_urls

    def _swatch_image_helper(self, image_json):
        swatch_images = []
        for image in image_json:
            if image.get('variant'):
                self.image_names.append(image['variant'])
            if image.get('hiRes') and image['hiRes'].strip():
                swatch_images.append(image['hiRes'])
            elif image.get('large') and image['large'].strip():
                swatch_images.append(image['large'])
        return swatch_images

    def _image_urls(self):
        if self.image_urls_checked:
            return self.image_urls

        self.image_urls_checked = True

        try:
            swatch_images = []

            page_raw_text = html.tostring(self.tree_html)

            swatch_image_json = re.search("var data = {\s+\'colorImages\': { \'initial\': (\[.*?\])},\n", page_raw_text)

            if swatch_image_json:
                swatch_image_json = json.loads(swatch_image_json.group(1))
                swatch_images = self._swatch_image_helper(swatch_image_json)
            else:
                swatch_image_json = self._find_between(page_raw_text, 'data["colorImages"] = ', ';\n')

                if swatch_image_json:
                    swatch_image_json = json.loads(swatch_image_json)
                    selected_color = self.tree_html.xpath('//span[@class="selection"]/text()')

                    if selected_color:
                        selected_color = selected_color[0].strip()
                    else:
                        try:
                            selected_variations = json.loads(
                                re.search('selected_variations":({.*?})', page_raw_text).group(1))
                            selected_color = ' '.join(reversed(selected_variations.values()))
                        except:
                            selected_color = None

                    for color in swatch_image_json:
                        if color == selected_color or len(swatch_image_json) == 1:
                            swatch_images = self._swatch_image_helper(swatch_image_json[color])

                else:
                    swatch_image_json = re.search("'colorImages': { 'initial': ([^\n]*)},", page_raw_text)
                    if swatch_image_json:
                        swatch_image_json = json.loads(swatch_image_json.group(1))
                        swatch_images = self._swatch_image_helper(swatch_image_json)

            if swatch_images:
                self.image_urls = self._remove_no_image_available(swatch_images)
                return self.image_urls

        except:
            print traceback.format_exc()

        def is_video_url(url):
            return 'player' in url or \
                   'video' in url or \
                   'play-button' in url or \
                    url in (self._video_urls() or [])

        for xpath in ["//div[contains(@class,'verticalMocaThumb')]/span/img/@src", # TODO: example?
                "//span[@class='a-button-text']//img/@src", # The small images are to the left of the big image
                "//div[@id='thumbs-image']//img/@src", # The small images are below the big image
                "//div[@class='dp-meta-icon-container']//img/@src", # Amazon instant video
                "//td[@id='prodImageCell']//img/@src",
                "//div[contains(@id,'thumb-container')]//img/@src",
                "//div[contains(@class,'imageThumb')]//img/@src",
                "//div[contains(@id,'coverArt')]//img/@src",
                "//div[@id='masrw-thumbs-image']//img[@class='masrw-thumbnail']/@src",
                "//li[contains(@class,'a-spacing-small item')]//img/@src",
                "//div[@id='ebooks-img-canvas']/img/@src"]:

            image_urls = self.tree_html.xpath(xpath)
            if image_urls and not self.no_image(image_urls):
                image_urls = [i for i in image_urls if not is_video_url(i)]
                self.image_urls = self._get_origin_image_urls_from_thumbnail_urls(image_urls)
                return self.image_urls

    def _remove_no_image_available(self, image_urls):
        filtered_image_urls = []

        for image in image_urls:
            if 'no-img' in image:
                self.no_image_available = 1
            else:
                filtered_image_urls.append(image)

        if filtered_image_urls:
            return filtered_image_urls

    def _image_names(self):
        self._image_urls()
        return self.image_names or None

    def _no_image_available(self):
        self._image_urls()
        return self.no_image_available

    def _in_page_360_image_urls(self):
        full_image_urls = re.search('fullImageURLs":({.*?})', html.tostring(self.tree_html))
        if full_image_urls:
            image_urls_360 = []
            full_image_urls = json.loads(full_image_urls.group(1))
            for k in sorted(full_image_urls.iterkeys()):
                image_urls_360.append(full_image_urls[k])
            return image_urls_360

    # return 1 if the "no image" image is found
    def no_image(self, image_url):
        try:
            if len(image_url) > 0 and image_url[0].find("no-img") > 0:
                return 1
            if self._no_image(image_url[0]):
                return 1
        except Exception, e:
            print "image_urls WARNING: ", e.message
        return 0

    def _video_urls(self):
        video_url = self.tree_html.xpath('//script')  # [@type="text/javascript"]
        temp = []
        for v in video_url:
            st = str(v.xpath('.//text()'))
            r = re.findall("[\'\"]url[\'\"]:[\'\"](http://.+?\.mp4)[\'\"]", st)
            if r:
                temp.extend(r)
            ii = st.find("kib-thumb-container-")
            if ii > 0:
                ij = st.find('"', ii + 19)
                if ij - ii < 25:
                    vid = st[ii:ij]
                    viurl = self.tree_html.xpath('//div[@id="%s"]//img/@src' % vid)
                    if len(viurl) > 0:
                        temp.append(viurl[0])

        # Find video among the  small images.
        image_url = self.tree_html.xpath("//span[@class='a-button-text']//img/@src")
        if len(image_url) == 0:
            image_url = self.tree_html.xpath("//div[@id='thumbs-image']//img/@src")
        for v in image_url:
            if v.find("player") > 0 and not re.search('\.png$', v):
                temp.append(v)

        video_urls = re.findall('"url":"([^"]+.mp4)"', html.tostring(self.tree_html))
        for video in video_urls:
            if not video in temp:
                temp.append(video)

        try:
            data = json.loads(re.search('var data = ({.*?});', html.tostring(self.tree_html)).group(1))
            for video in data.get('videos', []):
                if not video['url'] in temp:
                    temp.append(video['url'])
        except:
            pass

        if len(temp) > 0:
            return temp

    def _video_count(self):
        if self._video_urls() == None:
            return len(self.tree_html.xpath('//*[@id="cr-video-swf-url" and not(@type="hidden")]'))
        return len(self._video_urls())

    def _best_seller_category(self):
        best_seller_cat = re.search('#[\d,]+ in ([^\(]+) \(', html.tostring(self.tree_html)) or \
                re.search('#[\d,]+ in ([^<]+)</span>', html.tostring(self.tree_html)) or \
                re.search('#?[\d\,\.]+ en ([^\(]+) \(', html.tostring(self.tree_html))
        if best_seller_cat:
            return best_seller_cat.group(1)

        best_seller_cat = self.tree_html.xpath('//div[@id="zeitgeistBadge_feature_div"]//a/@title') or \
                self.tree_html.xpath('//ul[@class="zg_hrsr"]//span[@class="zg_hrsr_ladder"]/a/text()')
        return best_seller_cat[0] if best_seller_cat else None

    def _size_chart(self):
        if self.tree_html.xpath('//a[@id="size-chart-url"]'):
            return 1
        return 0

    def _redirect(self):
        return self.is_redirect

    ##########################################
    ################ CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        for xpath in ["//span[@id='cmrsSummary-popover-data-holder']/@data-title",
                "//div[@class='gry txtnormal acrRating']//text()",
                "//div[@id='avgRating']//span//text()",
                "//*[contains(@class,'averageStarRating')]/span/text()",
                "//div[@id='revMHLContainer']//div[@id='summaryStars']//span/text()",
                "//div[@id='averageCustomerReviews']//span[@class='a-icon-alt']/text()"]:

            average_review = self.tree_html.xpath(xpath)

            if average_review:
                try:
                    return float(re.search(r'\d+[\.\,]\d+|\d+', average_review[0]).group().replace(',','.'))
                except Exception:
                    print traceback.format_exc()

    def _review_count(self):
        if self.is_prime:
            num_of_reviews_info = self.tree_html.xpath(
                "//div[@class='crIFrameHeaderHistogram']"
                "//div[@class='tiny']//text()")

            # Count of Review
            if num_of_reviews_info:
                num_of_reviews = re.match(r'(\d*\.?\d+)',
                                          str(self._clean_text(''.join(num_of_reviews_info).replace(',', '')))).group()
            else:
                num_of_reviews = 0

            return int(num_of_reviews)
        else:
            if not self.is_review_checked:
                self._reviews()
            if self.review_list and len(self.review_list) == 5:
                sumup = 0
                for i, v in self.review_list:
                    sumup += int(v)
                return sumup

            nr_reviews = self.tree_html.xpath("//span[@id='acrCustomerReviewText']//text()")
            if len(nr_reviews) > 0:
                nr_reviews = re.match('[\d,]+', nr_reviews[0])
                if nr_reviews:
                    return self._toint(nr_reviews.group())
            nr_reviews = self.tree_html.xpath("//div[@class='fl gl5 mt3 txtnormal acrCount']//text()")
            if len(nr_reviews) > 1:
                return self._toint(nr_reviews[1])
            nr_reviews = self.tree_html.xpath("//a[@class='a-link-normal a-text-normal product-reviews-link']//text()")
            if len(nr_reviews) > 1:
                return self._toint(nr_reviews[0].replace('(', '').replace(')', '').replace(',', ''))
            if self.scraper_version == "uk":
                nr_reviews = self.tree_html.xpath("//span[@class='crAvgStars']/a//text()")
                if len(nr_reviews) > 0:
                    res = nr_reviews[0].split()
                    return self._toint(res[0])
            return 0

    def _reviews(self):
        if self.is_review_checked:
            return self.review_list

        self.is_review_checked = True

        reviews_div = self.tree_html.xpath('//span[@id="cmrsSummary-popover-data-holder"]')
        if reviews_div:
            self.review_list = [
                [5,int(reviews_div[0].get('data-five-count'))],
                [4,int(reviews_div[0].get('data-four-count'))],
                [3,int(reviews_div[0].get('data-three-count'))],
                [2,int(reviews_div[0].get('data-two-count'))],
                [1,int(reviews_div[0].get('data-one-count'))],
            ]
            return self.review_list

        if not self._review_count():
            return

        if self.is_prime:
            rating_by_star = []
            rating_values = []
            rating_counts = []

            num_of_reviews = self._review_count()

            # Get mark of Review
            rating_values_data = self.tree_html.xpath("//div[contains(@class, 'histoRating')]//text()")
            if rating_values_data:
                for rating_value in rating_values_data:
                    rating_values.append(int(re.findall(r'(\d+)', rating_value[0])[0]))

            # Get count of Mark
            rating_count_data = self.tree_html.xpath("//div[contains(@class, 'histoCount')]//text()")
            if num_of_reviews:
                if rating_count_data:
                    for rating_count in rating_count_data:
                        rating_count = int(num_of_reviews) * int(re.findall(r'(\d+)', rating_count)[0]) / 100
                        rating_counts.append(int(format(rating_count, '.0f')))

            if rating_counts:
                rating_counts = rating_counts[::-1]

            for i in range(0, 5):
                ratingFound = False
                for rating_value in rating_values:
                    for index, attribute in enumerate(rating_counts):
                        if rating_value == i + 1:
                            if index == i:
                                rating_by_star.append([rating_value, rating_counts[index]])
                                ratingFound = True
                                break

                if not ratingFound:
                    rating_by_star.append([i + 1, 0])

            if rating_by_star:
                self.review_list = rating_by_star[::-1]
                self.review_count = int(num_of_reviews)

        else:
            review_list = []

            mark_list = ['five', 'four', 'three', 'two', 'one']

            found_review = False

            for index, mark in enumerate(mark_list):
                review_url = urlparse.urljoin(self.product_page_url, self.REVIEW_URL.format(self._product_id(), mark))

                for retry_index in range(self.REVIEW_RETRIES):
                    try:
                        resp = self._request(review_url, session=self.session, timeout=10)

                        if resp.ok:
                            contents = resp.text

                            no_reviews_strings = ['Sorry, no reviews match your current selections.',
                                                  u'Désolés, aucun commentaire ne correspond à vos sélections actuelles.',
                                                  u'No hay ninguna opini\xf3n con los criterios seleccionados.',
                                                  u'Leider stimmen keine Rezensionen mit ihrer derzeitiger Auswahl überein.',
                                                  u'抱歉，无评论满足您当前的筛选条件']

                            if any(no_reviews_string in contents for no_reviews_string in no_reviews_strings):
                                review_list.append([5 - index, 0])
                            else:
                                review_html = html.fromstring(contents)
                                review_count_text = review_html.xpath("//div[@id='cm_cr-review_list']"
                                                                      "//div[contains(@class, 'a-section a-spacing-medium')]"
                                                                      "//span[@class='a-size-base']/text()")

                                if review_count_text:
                                    review_count_regexes = [
                                        'of (.*) reviews',
                                        'de (.*) opiniones',
                                        'sur(.*)commentaires',
                                        'von (.*) Rezensionen werden angezeigt',
                                        u'条评论，共 (.*) 条评论'
                                    ]

                                    for review_count_regex in review_count_regexes:
                                        review_count = re.search(review_count_regex, review_count_text[0])
                                        if review_count:
                                            review_count = review_count.group(1)
                                            review_list.append([5 - index, self._toint(review_count)])
                                            found_review = True
                                else:
                                    if review_html.xpath('//title/text()')[0] == 'Robot Check':
                                        error = 'captcha'
                                    else:
                                        error = 'no reviews found'

                                    err_msg = 'Error extracting Amazon reviews: %s star, retry %d, error %s' % \
                                              (mark, retry_index, error)
                                    print err_msg

                                    if self.lh:
                                        self.lh.add_list_log('errors', err_msg)

                                    continue
                            break

                        else:
                            err_msg = 'Error extracting Amazon reviews: %s star, retry %d, error %s' % \
                                      (mark, retry_index, str(resp.status_code))
                            print err_msg

                            if self.lh:
                                self.lh.add_list_log('errors', err_msg)

                            if str(resp.status_code).startswith('4'):  # do not retry 4xx errors
                                break

                    except Exception, e:
                        print traceback.format_exc(e)

                        if self.lh and retry_index == self.REVIEW_RETRIES - 1:
                            err_msg = 'Error extracting Amazon reviews: %s star, error %s %s'
                            self.lh.add_list_log('errors', err_msg % (mark, type(e), str(e)))

            if review_list and found_review:
                self.review_list = review_list

        return self.review_list

    def _tofloat(self, s):
        try:
            s = s.replace(",", "")
            s = re.findall(r"[\d\.]+", s)[0]
            t = float(s)
            return t
        except ValueError:
            return 0.0

    def _toint(self, s):
        try:
            s = s.replace(',', '')
            t = int(s)
            return t
        except ValueError:
            return 0

    ##########################################
    ################ CONTAINER : SELLERS
    ##########################################
    def _price_currency(self):
        if self._price():
            if self.scraper_version == 'ca':
                return 'CAD'
            if self.scraper_version == 'cn':
                return 'CNY'
            if self.scraper_version in ['de', 'fr', 'es']:
                return 'EUR'
            if self.scraper_version == 'in':
                return 'INR'
            if self.scraper_version == 'mx':
                return 'MXN'
            if self.scraper_version == 'uk':
                return 'GDP'
            return 'USD'

    # extract product price from its product product page tree
    def _price(self):
        price_xpaths = ["//span[@id='priceblock_ourprice']",
                        "//span[@id='priceblock_dealprice']",
                        "//span[@id='priceblock_saleprice']",
                        "//span[contains(@class, 'header-price')]",
                        "//div[@id='centerCol']//span[contains(@class, 'a-color-price')]"]

        price = None

        currency = u"$"
        if self.scraper_version == "ca":
            currency = u"CDN$"
        if self.scraper_version == "cn":
            currency = u"￥"
        if self.scraper_version in ["de", "fr", "es"]:
            currency = u"EUR"
        if self.scraper_version == "in":
            currency = u"₹"
        if self.scraper_version == "uk":
            currency = u"£"

        for pr_xpath in price_xpaths:
            try:
                price = self._clean_text(self.tree_html.xpath(pr_xpath)[0].text_content())
                if price:
                    price = price.replace(currency, '').strip()
                    if self.scraper_version in ["ca", "de", "fr", "es"]:
                        price = price.replace(",", ".").replace(u'\xa0', '')

                    if 'dealprice' in pr_xpath or 'saleprice' in pr_xpath:
                        self.temp_price_cut = 1
                    break
            except:
                continue

        # skip empty prices or 'Currently unavailable.', 'Out of Print' etc:
        # (https://www.amazon.com/dp/0131129708, https://www.amazon.com/dp/0131068008)
        if not price or not price[0].isdigit():
            return

        if "-" in price:
            if currency not in price:
                price = currency + price.split("-")[0].strip() + u"-" + currency + price.split("-")[1].strip()
            else:
                price = price.split("-")[0].strip() + u"-" + price.split("-")[1].strip()
        else:
            if currency not in price:
                price = currency + price

        return price

    def _temp_price_cut(self):
        return self.temp_price_cut

    def _subscribe_discount(self):
        """
        Parses product subscribe & save discount percentage.
        """
        percent_ss = self.tree_html.xpath('//*[contains(@class, "snsSavings")]/text()')
        if not percent_ss:
            percent_ss = self.tree_html.xpath('//*[contains(@id, "regularprice_savings")]//text()')
        if percent_ss:
            percent_ss = re.findall('\((.*)\)', percent_ss[0])
        else:
            percent_ss = self.tree_html.xpath('//span[@class="discountTextLeft"]/text()')
        if percent_ss:
            try:
                percent_ss = float(percent_ss[0].replace('%', ''))
                return percent_ss
            except:
                print "Subscribe Discount Error"

    def _subscribe_price(self):
        """
        Parses product price subscribe and save.
        """
        price_ss = self.tree_html.xpath('//*[contains(@class, "snsSavings")]/text()')
        if not price_ss:
            price_ss = self.tree_html.xpath('//*[contains(@id, "subscriptionPrice")]/text()')
        if price_ss:
            price_ss = re.findall('\$\d{1,3}[,\.\d{3}]*\.?\d*', price_ss[0])
            try:
                price_ss = float(price_ss[0].replace('$', ''))
                return price_ss
            except:
                print "Subscribe Price Error"

    def _in_stores(self):
        return 0

    def _marketplace(self):
        aa = self.tree_html.xpath("//div[@class='buying' or @id='merchant-info']")
        for a in aa:
            if a.text_content().find('old by ') > 0 and a.text_content().find('old by Amazon') < 0:
                return 1
            if a.text_content().find('seller') > 0:
                return 1
        a = self.tree_html.xpath('//div[@id="availability"]//a//text()')
        if len(a) > 0 and a[0].find('seller') >= 0:
            return 1

        marketplace_sellers = self._marketplace_sellers()

        if marketplace_sellers:
            return 1

        if self.tree_html.xpath(
                "//div[@id='toggleBuyBox']//span[@class='a-button-text' and text()='Shop This Website']"):
            return 1

        s = self._seller_from_tree()
        return s['marketplace']

    def _primary_seller(self):
        if re.search('Dispatched from and sold by Amazon', html.tostring(self.tree_html)):
            return 'Amazon.co.uk'

        seller = re.search(
            r'Ships from and sold by (Amazon.com|AmazonFresh|Prime Now LLC)',
            html.tostring(self.tree_html)
        )
        if seller:
            return seller.group(1)

        merchant_info = self.tree_html.xpath('//div[contains(@id, "merchant-info")]/a/text()')

        if merchant_info:
            return merchant_info[0]

        marketplace_sellers = self._marketplace_sellers()

        if marketplace_sellers:
            return marketplace_sellers[0]

    def _marketplace_sellers(self):
        if self.is_marketplace_sellers_checked:
            return self.marketplace_sellers

        self.is_marketplace_sellers_checked = True

        sellers = self.tree_html.xpath('//div[@id="moreBuyingChoices_feature_div"]//div[@class="a-row"]')

        if sellers:
            self.marketplace_sellers = []
            self.marketplace_prices = []

            for s in sellers:
                try:
                    name = s.xpath('.//span[contains(@class,"mbcMerchantName")]/text()')[0].strip()
                    self.marketplace_sellers.append(name)

                    price = s.xpath('.//span[contains(@class,"a-color-price")]/text()')[-1].strip()
                    self.marketplace_prices.append(price)
                except:
                    break

            return self.marketplace_sellers

        mps = []
        mpp = []
        path = '/tmp/amazon_sellers.json'

        try:
            with open(path, 'r') as fp:
                amsel = json.load(fp)
        except:
            amsel = {}

        domain = self.product_page_url.split("/")

        try:
            url = domain[0] + "//" + domain[2] + "/gp/offer-listing/" + \
                  self.tree_html.xpath("//input[@id='ASIN']/@value")[0] + "/ref=olp_tab_all"
        except:
            url = domain[0] + "//" + domain[2] + "/gp/offer-listing/" + self._product_id() + "/ref=olp_tab_all"
        fl = 0

        while len(url) > 10:
            contents = self._request(url).text
            tree = html.fromstring(contents)
            sells = tree.xpath('//div[@class="a-row a-spacing-mini olpOffer"]')

            for s in sells:
                price = s.xpath('.//span[contains(@class,"olpOfferPrice")]//text()')
                sname = s.xpath('.//*[contains(@class,"olpSellerName")]/span/a/text()')

                if len(price) > 0:
                    seller_price = self._tofloat(price[0])
                    seller_name = ""

                    if len(sname) > 0 and sname[0].strip() != "":
                        seller_name = sname[0].strip()
                    else:
                        seller_link = s.xpath(".//p[@class='a-spacing-small']/a/@href")

                        if len(seller_link) > 0:
                            sd = seller_link[0].split("/")
                            seller_id = ""

                            if len(sd) > 4:
                                seller_id = sd[4]
                                #                                print "seller_id",seller_id

                                if seller_id != "" and seller_id in amsel:
                                    seller_name = amsel[seller_id]
                                    #                                    print "seller_name",seller_name

                            if seller_name == "":
                                seller_link = urllib.urljoin(self.product_page_url, seller_link[0])
                                seller_content = self._request(seller_link).text

                                seller_tree = html.fromstring(seller_content)
                                seller_names = seller_tree.xpath("//h2[@id='s-result-count']/span/span//text()")

                                if len(seller_names) > 0:
                                    seller_name = seller_names[0].strip()
                                else:
                                    seller_names = seller_tree.xpath("//title//text()")

                                    if len(seller_names) > 0:
                                        if seller_names[0].find(":") > 0:
                                            seller_name = seller_names[0].split(":")[1].strip()
                                        else:
                                            seller_name = seller_names[0].split("@")[0].strip()

                            if seller_name != "" and seller_id != "":
                                amsel[seller_id] = seller_name
                                fl = 1

                    if seller_name != "":
                        mps.append(seller_name)
                        mpp.append(seller_price)

                        if len(mps) > 20:
                            break

            if len(mps) > 20:
                break

            urls = tree.xpath(".//ul[contains(@class,'a-pagination')]//li[contains(@class,'a-last')]//a/@href")

            if len(urls) > 0:
                url = domain[0] + "//" + domain[2] + urls[0]
            else:
                url = ""

        if len(mps) > 0:
            if fl == 1:
                try:
                    with open(path, 'w') as fp:
                        json.dump(amsel, fp)
                except Exception as ex:
                    print ex

            self.marketplace_prices = mpp
            self.marketplace_sellers = mps

            return mps

    def _marketplace_prices(self):
        self._marketplace_sellers()

        return self.marketplace_prices

    def _marketplace_lowest_price(self):
        self._marketplace_sellers()

        return min(self.marketplace_prices) if self.marketplace_prices else None

    # extract product seller information from its product product page tree (using h2 visible tags)
    def _seller_from_tree(self):
        seller_info = {}
        h5_tags = map(lambda text: self._clean_text(text), self.tree_html.xpath("//h5//text()[normalize-space()!='']"))
        acheckboxlabel = map(lambda text: self._clean_text(text),
                             self.tree_html.xpath("//span[@class='a-checkbox-label']//text()[normalize-space()!='']"))
        seller_info['owned'] = 1 if "FREE Two-Day" in acheckboxlabel else 0

        a = self.tree_html.xpath('//div[@id="soldByThirdParty"]')
        a = not not a  # turn it into a boolean
        seller_info['marketplace'] = 1 if "Other Sellers on Amazon" in h5_tags else 0
        seller_info['marketplace'] = int(seller_info['marketplace'] or a)

        return seller_info

    def _owned(self):
        owned = self.tree_html.xpath('//input[@id="sellingCustomerID" and @value="A2R2RITDJNW1Q6"]')
        return 1 if owned else 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if not self._site_online():
            return

        if self._no_longer_available():
            return 1

        try:
            self._product_name()
        except:
            return 1

        return 0

    ##########################################
    ################ CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
            "//div[@id='wayfinding-breadcrumbs_feature_div']//ul//a[@class='a-link-normal a-color-tertiary']/text()")
        categories = [category.strip() for category in categories]

        if categories:
            return categories

        if self._seller_ranking():
            return self._seller_ranking()[-1].get('category').split(' > ')

        nav = self.tree_html.xpath('//span[@class="nav-search-label"]/text()')
        if nav and nav[0] != 'All':
            return nav

    def _brand(self):
        xpaths = [
            '//div[@id="mbc"]/@data-brand',
            '//*[@id="brand"]//text()',
            '//div[@class="buying"]//span[contains(text(),"by")]/a//text()',
            '//a[contains(@class,"contributorName")]//text()',
            '//a[contains(@id,"contributorName")]//text()',
            '//span[contains(@class,"author")]//a//text()',
            '//div[@id="ArtistLinkSection"]//text()',
            '//td[@class="label" and contains(text(), "Brand")]/following-sibling::td[@class="value"]/text()',
            '//a[@id="bylineInfo"]/text()'
        ]

        for xpath in xpaths:
            brand = self.tree_html.xpath(xpath)
            if brand:
                brand = brand[0].strip()
                if brand:
                    return brand

        for f in (self._features() or []):
            if f.find("Studio:") >= 0 or f.find("Network:") >= 0:
                return f.split(':')[1]

        return guess_brand_from_first_words(self._product_name())

    def _version(self):
        return self.scraper_version

    def _fresh(self):
        fresh = self.tree_html.xpath("//div[@id='availability_feature_div']"
                                     "//div[@id='fresh-merchant-info']/text()")
        return 1 if fresh else 0

    def _pantry(self):
        pantry_info = self.tree_html.xpath("//div[@id='price']//img/@alt")
        pantry_logo = self.tree_html.xpath("//a[contains(@class, 'pantry-logo')]/@href")

        if (pantry_info and 'Pantry' in pantry_info[0]) or pantry_logo:
            return 1
        return 0

    def _marketing_content(self):
        marketing_content = ''

        aplus_modules = self.tree_html.xpath("//div[contains(@cel_widget_id,'aplus-module-')]")
        for aplus_module in aplus_modules:
            marketing_content += html.tostring(aplus_module)

        if marketing_content:
            return re.sub('\s+', ' ', marketing_content)

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        text = super(AmazonScraper, self)._clean_text(text)
        text = HTMLParser().unescape(text)
        text = re.sub(u'\u009b', '', text)
        return text.strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "model": _model,
        "upc": _upc,
        "asin": _asin,
        "features": _features,
        "specs": _specs,
        "description": _description,
        "seller_ranking": _seller_ranking,
        "long_description": _long_description,
        "apluscontent_desc": _apluscontent_desc,
        "variants": _variants,
        "swatches": _swatches,
        "ingredients": _ingredients,
        "no_longer_available": _no_longer_available,
        "bullets": _bullets,
        "usage": _usage,
        "directions": _directions,
        "warnings": _warnings,
        "indications": _indications,
        "has_warning": _has_warning,
        "warning_text": _warning_text,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "image_names": _image_names,
        "in_page_360_image_urls": _in_page_360_image_urls,
        "no_image_available": _no_image_available,
        "video_count": _video_count,
        "video_urls": _video_urls,
        "canonical_link": _canonical_link,
        "best_seller_category": _best_seller_category,
        "size_chart": _size_chart,
        "redirect": _redirect,
        "fresh": _fresh,
        "pantry": _pantry,
        "marketing_content": _marketing_content,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "temp_price_cut": _temp_price_cut,
        "subscribe_price": _subscribe_price,
        "subscribe_discount": _subscribe_discount,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "marketplace_sellers": _marketplace_sellers,
        "marketplace_prices": _marketplace_prices,
        "marketplace_lowest_price": _marketplace_lowest_price,
        "primary_seller": _primary_seller,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "owned": _owned,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        "scraper": _version,
    }
