from product_ranking.spiders.levi import LeviProductsSpider


class LeviDEProductsSpider(LeviProductsSpider):
    name = 'levide_products'
    country = "DE"
    locale = "de_DE"
