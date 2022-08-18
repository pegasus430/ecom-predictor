from product_ranking.pet_base_class import PetBaseProductsSpider
from product_ranking.items import SiteProductItem


class Pet360ProductsSpider(PetBaseProductsSpider):
    name = 'pet360_products'
    allowed_domains = ['pet360.com']
    handle_httpstatus_list = [404]
    SEARCH_URL = ("https://www.pet360.com/sitesearch?w={search_term}")

    def _scrape_product_links(self, response):
        item_urls = response.css(
            '.item h2 > a::attr("href")').extract()

        for item_url in item_urls:
            yield item_url, SiteProductItem()