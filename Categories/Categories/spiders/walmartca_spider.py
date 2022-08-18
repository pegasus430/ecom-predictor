from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from Categories.items import CategoryItem
from Categories.items import ProductItem
from scrapy.http import Request
import sys
import re
import datetime
from scrapy import log

from spiders_utils import Utils

# minimum description length
DESC_LEN = 200
# minimum description paragraph length
DESC_PAR_LEN = 30

################################
# Run with 
#
# scrapy crawl walmart.ca
#
################################

# scrape sitemap and extract categories
class WalmartCaSpider(BaseSpider):
    name = "walmartca"
    allowed_domains = ["walmart.ca"]
    start_urls = [
        "http://www.walmart.ca/en",
    ]


    def __init__(self, outfile=None):
        self.root_url = "http://www.walmart.ca"
        self.outfile = outfile

        # set flag that indicates that for this spider, nr of products for each catgory should be computed
        self.compute_nrproducts = True

        # level that is considered to contain departments
        self.DEPARTMENT_LEVEL = 1

        # keep crawled items represented by (url, parent_url, department_url) pairs
        # to eliminate duplicates
        # (adding department_url makes sure that if one entire department is found as a subcategory of another for ex, both (and their complete category trees) will be crawled)
        self.crawled = []

        # last used category id, used for autoincrementing ids idenrifying categories
        self.id_count = 0

        # hardcoded values for special category's item count. Currently used for 'Value of the day' that typically has fixed number of products, and nowhere to extract it from page
        self.special_itemcount = {'value of the day' : 2}

    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        #links = hxs.select("//div[@class='MidContainer']/div[3]//a[@class='NavM']")
        #parent_links = hxs.select("//div[@class='MidContainer']/div[3]//a[@class='NavXLBold']")
        #parent_links = hxs.select("//div[@class='MidContainer']/div/div/div[not(@class)]//a[@class='NavXLBold']")

        parent_links = hxs.select("//div[@class='linkGroup']/div[not (@class)]/a[@class='NavXLBold'][@href]")

            # #TODO: check this
            # item['nr_products'] = -1
            # yield item
            #yield Request(item['url'], callback = self.parseCategory, meta = {'item' : item})

        department_id = 0

        for link in parent_links:
            item = CategoryItem()

            #TO remove:
            # # link to artificial parent category
            # item['parent_catid'] = 0

            item['text'] = link.select('text()').extract()[0]
            item['url'] = link.select('@href').extract()[0]

            # add domain if relative URL
            item['url'] = Utils.add_domain(item['url'], self.root_url)

            item['level'] = 1

            department_id += 1

            # send category page to parseCategory function to extract description and number of products and add them to the item
            yield Request(item['url'], callback = self.parseCategory, meta = {'item' : item, \
                'department_text' : item['text'], 'department_url' : item['url'], 'department_id' : department_id})

    # parse category page and extract description and number of products
    def parseCategory(self, response):

        # URLs like health.walmart.com don't have body_as_unicode and generate an exception
        try:
            hxs = HtmlXPathSelector(response)
        except AttributeError, e:
            self.log("Could not get response from " + response.url + "; original exception: " + str(e) + "\n", level=log.WARNING)
            return

        item = response.meta['item']

        # Add department text, url and id to item
        item['department_text'] = response.meta['department_text']
        item['department_url'] = response.meta['department_url']
        item['department_id'] = response.meta['department_id']

        # assign unique id
        item['catid'] = self.id_count
        self.id_count += 1

     
        # Extract subcategories breakdown if any ("classification" field)
        classification_criteria = hxs.select("//form[@id='refine']//h6[@class='AdvSearchSubhead']")
        classification_dictionary = {}
        for criterion in classification_criteria:
            criterion_name = criterion.select(".//text()[normalize-space()!='']").extract()[0].strip()
            # extract subcategories by this criterion:
            # find first subcategories list element following this criterion name, ignore if subcategory text starts with "See " ("See fewer", "See more")
            subcategories = criterion.select("following-sibling::div[contains(@class,'accordionContainer')][1]/ul[@class='MainMenu AdvSearchMenu']/li/a[not(contains(text(), 'See '))]")
            # then filter by regex only ones whose text contains at least one letter (for ex, for customers rating subcats, they have no name, only a picture with nr of starts, we don't want them)
            subcategories = filter(lambda x: x.select("text()").re(".*[A-Za-z]+.*"), subcategories)

            # if we found these, create the classification dictionary
            if criterion_name and subcategories:
                subcategories_list = []
                for subcategory in subcategories:
                    subcategory_name = subcategory.select("@title").extract()[0]
                    # replace &nbsp with space, trim
                    subcategory_name = subcategory_name.replace("&nbsp"," ").strip()
                    # extract product count
                    subcategory_prodcount = subcategory.select("span[@class='count']/text()").extract()
                    # if there is no count field, extract prodcount from subcategory name
                    if subcategory_prodcount:
                        m = re.match("\(([0-9]+)\)",subcategory_prodcount[0].strip())
                        # eliminate parantheses surrounding number and convert to int
                        if m:
                            subcategory_prodcount = m.group(1)
                        else:
                            subcategory_prodcount = subcategory_prodcount[0].strip()
                    else:
                        # if there is no product count in separate element, try to extract it from subcategory name
                        subcategory_name = subcategory.select(".//text()[normalize-space()!='']").extract()[0].replace("&nbsp", " ").replace(u"\xa0", " ").strip()
                        m = re.match("(.*)\(([0-9]+)\)", subcategory_name)
                        if m:
                            subcategory_prodcount = m.group(2)
                            subcategory_name = m.group(1).strip()
                            
                    if subcategory_name and subcategory_prodcount:
                        subcategory_item = {"name": subcategory_name, "nr_products": int(subcategory_prodcount)}
                        subcategories_list.append(subcategory_item)

                classification_dictionary[criterion_name] = subcategories_list

        if classification_dictionary:
            item['classification'] = classification_dictionary


        ##########################################################################################
        #
        # Extract description title, text, wordcount, and keyword density (if any)


        ###########################################
        #TODO:

        # first search for the description id they usually use,
        # second one is used more rarely and also with some false positives so needs to be checked for text length as well
        # try to find div with detailedPageDescriptionCopyBlock id; move on only if not found
        description_holder = hxs.select("//div[@id='detailedPageDescriptionCopyBlock']")

        # flag to tell if we found it with basic rule
        found = True

        if not description_holder:
            found = False
            description_holder = hxs.select("//div[@class='CustomPOV ReminderBubbleSeeAll']//p/text()[string-length() > " + str(DESC_LEN) + "]/parent::*/parent::*")

        # if none was found, try to find an element with much text (> DESC_LEN (200) characters)
        # this is gonna pe a paragraph in the description, look for its parent (containing the entire description)
        if not description_holder:
            #description_holder = hxs.select("//*[not(self::script or self::style)]/text()[string-length() > " + str(DESC_LEN) + "]/parent::*/parent::*")
            #TODO: !!does this mean string length for one paragraph is > DESC_LEN, or string length for entinre text content?
            # I think it means entire text content. We're ok
            description_holder = hxs.select("//p/text()[string-length() > " + str(DESC_LEN) + "]/parent::*/parent::*")

        # select element among these with most text
        if description_holder:
            desc_winner = description_holder[0]
            max_text = 0
            for desc_candidate in description_holder:
                # consider only text that is under a <p> tag and that has more than DESC_PAR_LEN (30) characters - then it's likely a description paragraph
                description_texts = desc_candidate.select(".//p//text()[string-length()>" + str(DESC_PAR_LEN) + "]").extract()
                text_len = len(" ".join(description_texts))
                if text_len > max_text:
                    max_text = text_len
                    desc_winner = desc_candidate
                # if text length is the same, assume one of them is parent of the other
                #  and select the one with greater depth (fewer children)
                elif text_len == max_text and text_len != 0:
                    children_old = float(desc_winner.select("count(*)").extract()[0])
                    children_new = float(desc_candidate.select("count(*)").extract()[0])
                    if children_new < children_old:
                        desc_winner = desc_candidate

            description_holder = desc_winner


        # try to find description title in <b> tag in the holder;
        # if it's not found, try to find it in the first <p> if the description
        # if found there, exclude it from the description body
        if description_holder:
            #TODO:
            # try this instead: ".//p//b/text() | .//h1/text() | .//h3/text() | .//strong/text() "
            # to fix Money Center problem. but maybe it's not always inside p?
            description_title = description_holder.select(".//b/text() | .//h1/text() | .//h3/text() | .//strong/text() ").extract()
            if description_title:
                # this will implicitly get thle first occurence of either a <b> element or an <h1> element,
                # which is likely to be the title (the title usually comes first)
                item['description_title'] = description_title[0].strip()

            description_texts = description_holder.select("./div[position()<2]//p//text()[not(ancestor::b) and not(ancestor::h1) and not(ancestor::strong)] \
                | ./p//text()[not(ancestor::b) and not(ancestor::h1) and not(ancestor::strong)]").extract()

            # if the list is not empty and contains at least one non-whitespace item
            if description_texts and reduce(lambda x,y: x or y, [line.strip() for line in description_texts]):
                description_text = " ".join([re.sub("\s+"," ", description_text.strip()) for description_text in description_texts if description_text.strip()])

                # if it's larger than 4096 characters and not found with main rule it's probably not a descriptions; causes problem to PHP script as well. Ignore it
                if len(description_text) < 4096 or found:

                    # replace all whitespace with one space, strip, and remove empty texts; then join them
                    item['description_text'] = description_text

                    # replace line breaks with space
                    item['description_text'] = re.sub("\n+", " ", item['description_text'])

            if 'description_text' in item:
                tokenized = Utils.normalize_text(item['description_text'])
                item['description_wc'] = len(tokenized)

                # sometimes here there is no description title because of malformed html
                # if we can find description text but not description title, title is probably malformed - get first text in div instead
                if 'description_title' not in item:
                    desc_texts = description_holder.select("./text()").extract()
                    desc_texts = [text for text in desc_texts if text.strip()]
                    if desc_texts:
                        item['description_title'] = desc_texts[0].strip()

                if 'description_title' in item:
                    (item['keyword_count'], item['keyword_density']) = Utils.phrases_freq(item['description_title'], item['description_text'])

            else:
                item['description_wc'] = 0

        else:
            item['description_wc'] = 0

        #
        ##################################################################################



        # Extract product count

        # find if there is a wc field on the page
        wc_field = hxs.select("//div[@class='mrl mod-toggleItemCount']/span/text() |\
            //div[@class='SPRecordCount']/text()").extract()
        if wc_field:
            m1 = re.match("([0-9]+) Results", wc_field[0])
            if m1:
                item['nr_products'] = int(m1.group(1))
            m2 = m2 = re.match("\s*Items\s*[0-9\-]+\s*of\s*([0-9]+)\s*total\s*", wc_field[0])
            if m2:
                item['nr_products'] = int(m2.group(1))

        # set item count for special items (hardcoded in special_itemcount)
        if item['text'].lower() in self.special_itemcount:
            item['nr_products'] = self.special_itemcount[item['text'].lower()]


        # Extract subcategories if no product count found
        if 'nr_products' in item:
            yield item

        else:
            # look for links to subcategory pages in menu
            subcategories_links = hxs.select("//div[contains(@class, 'G1001 LeftNavRM')]/div[contains(@class, 'yuimenuitemlabel browseInOuter')]/a[@class='browseIn']")

            if not subcategories_links:
            # # if we haven't found them, try to find subcategories in menu on the left under a "Shop by Category" header
            #     subcategories_links = hxs.select("//div[@class='MainCopy']/div[@class='Header' and text()='\nShop by Category']/following-sibling::node()//a")

            # if we haven't found them, try to find subcategories in menu on the left - get almost anything
                subcategories_links = hxs.select("//div[@class='MainCopy']/div[@class='Header' and not(contains(text(),'Related Categories')) \
                    and not(contains(text(),'Special Offers')) and not(contains(text(),'View Top Registry Items')) and not(contains(text(),'Featured Content'))\
                    and not(contains(text(), 'Featured Brands'))]\
                    /following-sibling::node()//a")
            
            # if we found them, create new category for each and parse it from the beginning

            #TODO
            ########################################
            # Exceptions - doesn't find anything for:
            #   http://photos.walmart.com/walmart/welcome?povid=cat121828-env999999-moduleA072012-lLinkGNAV5_PhotoCenter
            #
            #
            ########################################

            if subcategories_links:

                # new categories are subcategories of current one - calculate and store their level
                parent_item = item
                level = parent_item['level'] - 1


                #print "URL ", response.url, " CALLING PARSEPAGE"
                for subcategory in subcategories_links:

                    # to avoid rescraping categories reached from links in menu and reaching levels of -9,
                    # if level < -3 assume we've been there and skip

                    if level < -3:
                        continue

                    item = CategoryItem()
                    item['url'] = Utils.add_domain(subcategory.select("@href").extract()[0], self.root_url)
                    text = subcategory.select("text()").extract()

                    if text:
                        item['text'] = text[0].strip()
                    else:
                        # usually means it's something else than what we need
                        #TODO: check
                        continue
                        #print "no text for subcategory ", item, response.url

                    # # take care of unicode
                    # item['text'] = item['text'].encode("utf-8", errors=ignore)

                    item['level'] = level

                    item['parent_text'] = parent_item['text']
                    item['parent_url'] = parent_item['url']
                    item['parent_catid'] = parent_item['catid']

                    if 'parent_text' in parent_item:
                        item['grandparent_text'] = parent_item['parent_text']
                    if 'parent_url' in parent_item:
                        item['grandparent_url'] = parent_item['parent_url']

                    # if parent's parents are missing, level must be at least 0
                    if 'parent_text' not in parent_item or 'parent_url' not in parent_item:
                        assert level >= 0

                    # send subcategory items to be parsed again
                    # if not already crawled
                    if (item['url'], item['parent_url'], response.meta['department_url']) not in self.crawled:
                        yield Request(item['url'], callback = self.parseCategory, meta = {'item' : item, \
                            'department_text' : response.meta['department_text'], 'department_url' : response.meta['department_url'], 'department_id' : response.meta['department_id']})
                        self.crawled.append((item['url'], item['parent_url'], response.meta['department_url']))

                # return current item
                # idea for sending parent and collecting nr products. send all of these subcats as a list in meta, pass it on, when list becomes empty, yield the parent
                yield parent_item
                    #yield Request(item['url'], callback = self.parsePage, meta = {'item' : item, 'parent_item' : parent_item})




            # if we can't find either products on the page or subcategory links
            else:
                #print "URL", response.url, " NO SUBCATs"
                #item['nr_products'] = 0
                yield item


    # parse a product page and calculate number of products, accumulate them from all pages
    def parsePage(self, response):

        #print "IN PARSEPAGE"
        hxs = HtmlXPathSelector(response)
        item = response.meta['item']

        if 'parent_item' in response.meta:
            parent_item = response.meta['parent_item']
            item['parent_text'] = parent_item['text']
            item['parent_url'] = parent_item['url']
            if 'parent_text' in parent_item:
                item['grandparent_text'] = parent_item['parent_text']
                item['grandparent_url'] = parent_item['parent_url']
            if 'nr_products' not in parent_item:
                parent_nr_products = 0
            else:
                parent_nr_products = parent_item['nr_products']

        # initialize product URL list
        if 'products' not in response.meta:
            products = []
        else:
            products = response.meta['products']

        # # if this is the first page, initialize number of products
        # if 'nr_products' not in item:
        #     old_nr_products = 0
        # else:
        #     old_nr_products = item['nr_products']

        # find number of products on this page
        product_links = hxs.select("//a[@class='prodLink ListItemLink']/@href").extract()

        # gather all products in this (sub)category
        products += product_links

        #this_nr_products = len(product_links)

        #item['nr_products'] = old_nr_products + this_nr_products
        # if 'parent_item' in response.meta:
        #     parent_item['nr_products'] = parent_nr_products + item['nr_products']
        # find URL to next page, parse it as well
        next_page = hxs.select("//a[@class='link-pageNum' and text()=' Next ']/@href").extract()
        if next_page:
            page_url = Utils.add_domain(next_page[0], self.root_url)
            request = Request(url = page_url, callback = self.parsePage, meta = {'item' : item, 'products' : products})
            if 'parent_item' in response.meta:
                request.meta['parent_item'] = parent_item
            yield request

        # if no next page, return current results; and return parent category page
        else:

            item['nr_products'] = len(set(products))
            yield item

            # #TODO: this is not good - when should we yield parent category?
            # if 'parent_item' in response.meta:
            #     yield parent_item

################################
# Run with 
#
# scrapy crawl bestseller [-a inspect=1]
#
################################

# scrape bestsellers lists and extract products
class BestsellerSpider(BaseSpider):
    name = "walmart_bestseller"
    allowed_domains = ["walmart.com"]
    start_urls = [
        "http://www.walmart.com/cp/Best-Sellers/1095979",
    ]
    root_url = "http://www.walmart.com"

    def __init__(self, inspect=False):
        self.inspect = inspect

    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        # select list of bestsellers departments
        dept_list = hxs.select("//div[@class='MainCopy']")[1]

        # select departments
        departments = dept_list.select("ul/li/a")

        for department in departments:

            # extract departments and pass them to parseDepartment function to parse list for each of them
            dept = department.select("text()").extract()[0]
            dept_url = department.select("@href").extract()[0]

            url = self.root_url + dept_url
            request = Request(url, callback = self.parseDepartment)
            request.meta['department'] = dept

            yield request

    def parseDepartment(self, response):

        # some of the products are duplicates across departments, they will only appear once on the final list

        hxs = HtmlXPathSelector(response)

        department = response.meta['department']

        #TODO: what if there is pagination? haven't encountered it so far

        products = hxs.select("//div[@class='prodInfo']")

        # counter to keep track of product's rank
        rank = 0

        for product in products:
            item = ProductItem()

            # if inspect option was activated, add info on the context of the product element on the page
            if self.inspect:
                item['prod_context'] = product.select("ancestor::*[1]").extract()

            rank += 1
            item['rank'] = str(rank)

            product_link = product.select("div[@class='prodInfoBox']/a[@class='prodLink ListItemLink']")

            product_name = product_link.select("text()").extract()
            product_url = product_link.select("@href").extract()

            if product_name:
                item['list_name'] = product_name[0]

            if product_url:
                item['url'] = self.root_url + product_url[0]
            else:
                # if there's no url move on to the next product
                continue

            item['department'] = department

            #TODO: some of the products have the "From" prefix before the price, should I include that?
            price_div = product.select(".//div[@class='camelPrice'] | .//span[@class='camelPrice']")
            price1 = price_div.select("span[@class='bigPriceText2']/text()").extract()
            price2 = price_div.select("span[@class='smallPriceText2']/text()").extract()

            if price1 and price2:
                item['price'] = price1[0] + price2[0]

            #TODO: include out of stock products? :
            else:
                price1 = price_div.select("span[@class='bigPriceTextOutStock2']/text()").extract()
                price2 = price_div.select("span[@class='smallPriceTextOutStock2']/text()").extract()

                if price1 and price2:
                    item['price'] = price1[0] + price2[0]

            #TODO: are list prices always retrieved correctly?
            listprice = product.select(".//div[@class='PriceMLtgry']/text").extract()
            if listprice:
                item['listprice'] = listprice[0]

            item['bspage_url'] = response.url

            # pass the item to the parseProduct method
            request = Request(item['url'], callback = self.parseProduct)
            request.meta['item'] = item

            yield request

    def parseProduct(self, response):
        hxs = HtmlXPathSelector(response)

        item = response.meta['item']

        product_name = hxs.select("//h1[@class='productTitle']/text()").extract()[0]
        item['product_name'] = product_name

        page_title = hxs.select("//title/text()").extract()[0]

        # remove "Walmart.com" suffix from page title
        m = re.match("(.*) [:-] Walmart\.com", page_title, re.UNICODE)
        if m:
            page_title = m.group(1).strip()


        # there are other more complicated formul as as well, we're not removing them anymore, the product name is enough on this case
        # "Purchase the ... for a low price at Walmart.com"
        # m1 = re.match("(.*) for less at Walmart\.com\. Save money\. Live better\.", page_title, re.UNICODE)
        # if m1:
        #     page_title = m1.group(1).strip()

        # m2 = re.match("(.*) at an always low price from Walmart\.com\. Save money\. Live better\.", page_title, re.UNICODE)
        # if m2:
        #     page_title = m2.group(1).strip()

        # m3 = re.match("(.*) at Walmart\.com\. Save money\. Live better\.", page_title, re.UNICODE)
        # if m3:
        #     page_title = m3.group(1).strip()

        item['page_title'] = page_title

        # add date
        item['date'] = datetime.date.today().isoformat()

        yield item