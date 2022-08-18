import re
import json
import traceback
import time

from product_ranking.spiders.cvs import CvsProductsSpider
from product_ranking.utils import _init_chromium
from scrapy import Request


class CvsShelfPagesSpider(CvsProductsSpider):
    name = 'cvs_shelf_urls_products'
    allowed_domains = ["cvs.com", "api.bazaarvoice.com"]

    shelf_payload = {
        "query": "",
        "fields": ["*"],
        "refinements": [],
        "wildcardSearchEnabled": False,
        "pruneRefinements": False,
        "area": "Production",
        "collection": "productsLeaf",
        "pageSize": 20,
        "visitorId": "cj9ri3sif00013lf1rumqwa0y",
        "sessionId": "cj9ri3sie00003lf1lbjp3y35",
    }

    def __init__(self, *args, **kwargs):
        super(CvsShelfPagesSpider, self).__init__(*args, **kwargs)
        self.product_url = kwargs['product_url']

        if "num_pages" in kwargs:
            self.num_pages = int(kwargs['num_pages'])
        else:
            self.num_pages = 1

        self.current_page = 1

    def start_requests(self):
        driver = None
        categories = None
        try:
            driver = _init_chromium()
        except:
            self.log("Could not get driver".format(traceback.format_exc()))

        if driver:
            try:
                driver.get(self.product_url)
                time.sleep(15)
                categories = self._extract_categories(driver)
            except:
                self.log("Cant start categories extraction: {}".format(traceback.format_exc()))
                if 'driver' in locals():
                    driver.quit()

        if categories:
            for i, category in enumerate(categories):
                self.shelf_payload["refinements"].append({"navigationName": "categories.{}".format(i + 1),
                                                          "type": "Value", "value": category})

            yield Request(self.SEARCH_URL, method='POST',
                          body=json.dumps(self.shelf_payload),
                          meta={'remaining': self.quantity, 'search_term': '', 'payload': self.shelf_payload},
                          headers=self.HEADERS)

    @staticmethod
    def _extract_categories(driver):
        categories = [category.text for category in driver.find_elements_by_xpath('//nav[@aria-label="Breadcrumbs"]/ul/li')]
        categories = [re.sub(r'\(.+?\)', '', category).strip() for category in categories]
        categories = [x for x in categories if x not in ('Home', 'Shop')]
        return categories

    def _scrape_next_results_page_link(self, response):
        if self.current_page < self.num_pages:
            self.current_page += 1
            return super(CvsShelfPagesSpider, self)._scrape_next_results_page_link(response)
