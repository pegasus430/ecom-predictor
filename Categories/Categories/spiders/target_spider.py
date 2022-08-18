from scrapy.spider import Spider
from scrapy.selector import Selector
from Categories.items import CategoryItem
from Categories.items import ProductItem
from scrapy.http import Request, FormRequest, Response, HtmlResponse
from scrapy import log

from spiders_utils import Utils
import re
import urllib
import json

# crawls sitemap and extracts department and categories names and urls (as well as other info)
class TargetSpider(Spider):
    name = "target"
    allowed_domains = ["target.com"]
    start_urls = [
        "http://www.target.com/c/more/-/N-5xsxf#?lnk=fnav_t_spc_3_31"
    ]

    def __init__(self):
        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1

        # only crawl down to this level
        self.LEVEL_BARRIER = -1

        # flag indicating whether to compute overall product counts in pipelines phase for this spider.
        # if on, 'catid' and 'parent_catid' fields need to be implemented
        self.compute_nrproducts = True

        # counter for department id, will be used to autoincrement department id
        self.department_count = 0
        # counter for category id
        self.catid = 0

        # base of urls on this site used to build url for relative links
        self.BASE_URL = "http://www.target.com"

        # maximum number of retries for getting data for dynamically generated content
        self.MAX_RETRIES_DYNCONT = 0

        # crawled urls - for an explicit duplicate filter. store seen (url, parent_url) pairs
        self.crawled_urls = []

    # extract departments and next level categories
    def parse(self, response):
        sel = Selector(response)

        departments = sel.xpath("//div[@class='ul-wrapper']/ul/li")

        for department in departments:

            # extract departments
            department_item = CategoryItem()
            department_item['text'] = department.xpath("a/text()").extract()[0].strip()
            department_item['url'] = self.build_url(department.xpath("a/@href").extract()[0])

            department_item['department_text'] = department_item['text']
            department_item['department_url'] = department_item['url']

            department_item['level'] = self.DEPARTMENT_LEVEL

            # assign next available department id
            self.department_count += 1
            department_item['department_id'] = self.department_count

            # assign next available category id
            self.catid += 1
            department_item['catid'] = self.catid

            # send to be parsed further
            yield Request(department_item['url'], callback = self.parseCategory, meta = {'item' : department_item})

            # extract its subcategories
            subcategories = department.xpath(".//li")
            for subcategory in subcategories:

                subcategory_item = CategoryItem()

                subcategory_item['text'] = subcategory.xpath("a/text()").extract()[0].strip()
                subcategory_item['url'] = self.build_url(subcategory.xpath("a/@href").extract()[0])

                # its level is one less than its parent's level
                subcategory_item['level'] = department_item['level'] - 1

                subcategory_item['department_text'] = department_item['department_text']
                subcategory_item['department_url'] = department_item['department_url']
                subcategory_item['department_id'] = department_item['department_id']

                subcategory_item['parent_text'] = department_item['text']
                subcategory_item['parent_url'] = department_item['url']
                subcategory_item['parent_catid'] = department_item['catid']

                # assign next available category id
                self.catid += 1
                subcategory_item['catid'] = self.catid

                # send to be parsed further
                yield Request(subcategory_item['url'], callback = self.parseCategory, meta = {'item' : subcategory_item})


    # extract category info given a category page url, extract its subcategories if necessary and return it
    def parseCategory(self, response):

        #TODO: add extraction of additional category info
        sel = Selector(response)

        #TODO: a lot of redirects. maybe for item, set 'url' to the one to which it was redirected? (response.url)
        item = response.meta['item']


        # Description extraction needs to be done first because it can be found in regular /c/ pages that are first passed to this method.
        # For other info (item count, subcategories), the spider will redirect to different page if necessary (where description won't be available)
        # extract description
        description_texts = sel.xpath("//div[@class='subpart']/p//text()").extract()

        # second try at finding descriptions
        if not description_texts:
            description_texts = sel.xpath("//div[@id='SEO_TEXT']//text()").extract()

        # replace all whitespace with one space, strip, and remove empty texts; then join them
        if description_texts:
            item['description_text'] = " ".join([re.sub("\s+"," ", description_text.strip()) for description_text in description_texts if description_text.strip()])

            tokenized = Utils.normalize_text(item['description_text'])
            item['description_wc'] = len(tokenized)

        else:
            item['description_wc'] = 0

        # try to extract item count - if alternative extraction needs to be done.
        # this item's parsing will be redirected through different method and returned here

        # extract item count
        nr_products_node = sel.xpath("//ul[@class='results']//strong/text()")
        if nr_products_node:
            # nr of products is in the second of these nodessel.xpath("//ul[@class='results']//strong/text()")
            nr_products = nr_products_node.extract()[1].strip()
            item['nr_products'] = int(nr_products)

        # alternative item count: try on same page, but with /sb/ instead of /c/ in url
        if not nr_products_node:
            m = re.match("http://www\.target\.com/c/(.*)", response.url)
            if m:
                new_url = "http://www.target.com/sb/" + m.group(1)

                # retry to this same method but with new url
                #TODO: will miss descriptions. leave it to the end of the method then. but I want subcats from that one too?
                #OR extract it in secondary method and send it back to original url
                yield Request(new_url, callback = self.parseCategory, meta = {'item' : item})

            else:
                if "/sb/" not in new_url:
                    print "DOES NOT MATCH", response.url

        # alternative item count extraction 2 (dynamically generated content)
        if not nr_products_node:

            # extract dynamycally loaded data by making an additional request (made by the page to load the data)
            # extract url and parameters from form data
            form = sel.xpath("//form[@name='dynamicAjaxFrm1']")
            if form:
                form_action = form.xpath("@action").extract()[0]
                form_inputs = form.xpath("input")
                # build string of parameters from input names and values
                param_dict = {form_input.xpath("@name").extract()[0] : form_input.xpath("@value").extract()[0] for form_input in form_inputs}
                param_string = urllib.urlencode(param_dict)
                # build url to make request to
                new_url = "http://www.target.com" + form_action + "&" + param_string

                # if this url was found, redirect request to new method to extract item count as well, that method will yield the item
                # only redirect to this method if we weren't already redirected from it - to avoid redirect loop
                if 'redirected' not in response.meta or not response.meta['redirected']:
                    yield Request(new_url, callback = self.parseCategoryDyncontent, meta = {'item' : item})
                    return


        #TODO: add description title as category name if no title available?
        # then also add the keyword/density count

        yield item

        if 'parent_url' in item:
            self.crawled_urls.append((item['url'], item['parent_url']))

        # extract subcategories (if we haven't reached level barrier)
        if item['level'] <= self.LEVEL_BARRIER:
            return

        parent_item = item

        # "shop categories" menu
        #subcategories = sel.xpath("//h3[text() = 'shop categories']/following-sibling::ul/li/a")
        #TODO: replace the not startswith with != ?
        subcategories_menu = sel.xpath("//h3[starts-with(text(), 'shop ') and not(starts-with(text(), 'shop by')) \
            and not(starts-with(text(), 'shop for')) and not(starts-with(text(), 'shop favorite')) and not(contains(text(), ' size'))]")
        subcategories = subcategories_menu.xpath("following-sibling::ul/li/a")

        for subcategory in subcategories:
            subcategory_item = CategoryItem()

            subcategory_item['text'] = subcategory.xpath("text()").extract()[0].strip()
            subcategory_item['url'] = self.build_url(subcategory.xpath("@href").extract()[0])

            # filter duplicates
            if (subcategory_item['url'], parent_item['url']) in self.crawled_urls:
                # print subcategory_item['url']
                # print parent_item['url']
                continue

            # assign next available category id
            self.catid += 1
            subcategory_item['catid'] = self.catid

            subcategory_item['level'] = parent_item['level'] - 1

            subcategory_item['parent_url'] = parent_item['url']
            subcategory_item['parent_text'] = parent_item['text']
            subcategory_item['parent_catid'] = parent_item['catid']

            subcategory_item['department_text'] = parent_item['department_text']
            subcategory_item['department_url'] = parent_item['department_url']
            subcategory_item['department_id'] = parent_item['department_id']

            # send this subcategory to be further parsed
            yield Request(subcategory_item['url'], callback = self.parseCategory, meta = {'item' : subcategory_item})

    # fill in item nr_products and pass it back to parseCategory; for items with dynamically generated content page
    # will be directed here from parseCategory through URL for page containing data that dynamically fills the product item page
    def parseCategoryDyncontent(self, response):
        item = response.meta['item']

        try:
            body = json.loads(response.body)
        except Exception:
            self.log("Ajax content could not be json decoded for " + response.url + " for item " + item['url'] + "\n", level=log.ERROR)

            # retry a number of times, store number of left retries in meta
            # after retries exhausted give up - return item back to method it came from, with flag in meta indicating its referrer method
            
            if 'retries' not in response.meta:
                retries = self.MAX_RETRIES_DYNCONT
            else:
                retries = response.meta['retries'] - 1

            if retries > 0:
                # retry
                #print "RETRYING FOR", item['url'], 'retries', retries
                return Request(item['url'], callback = self.parseCategoryDyncontent, meta = {'item' : item, 'redirected' : True, 'retries' : retries})
            else:
                # give up
                return Request(item['url'], callback = self.parseCategory, meta = {'item' : item, 'redirected' : True})

        #print "Ajax content could be json decoded for ", response.url, " for item ", item['url']

        content = body['PLP_For_Grid']

        new_response = HtmlResponse(response.url, body=content.encode("utf-8"))
        sel = Selector(new_response)
        
        nr_products_node = sel.xpath("//ul[@class='results']//strong/text()")
        if nr_products_node:
            # nr of products is in the second of these nodessel.xpath("//ul[@class='results']//strong/text()")
            nr_products = nr_products_node.extract()[1].strip()
            item['nr_products'] = int(nr_products)

        # return item back to parseCategory for the rest of product info to be extracted; set 'redirected' flag to avoid redirect loop
        return Request(item['url'], callback = self.parseCategory, meta = {'item' : item, 'redirected' : True})


    # build URL from relative links found on pages: add base url and clean final url
    def build_url(self, url):
        url = Utils.add_domain(url, self.BASE_URL)
        url = Utils.clean_url(url, ['#'])
        return url

