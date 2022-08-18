from product_ranking.pet_base_class import PetBaseProductsSpider


class PetfooddirectProductsSpider(PetBaseProductsSpider):
    name = 'petfooddirect_products'
    allowed_domains = ['petfooddirect.com']
    handle_httpstatus_list = [404]
    SEARCH_URL = ("https://www.petfooddirect.com/sitesearch?w={search_term}&view=grid")
