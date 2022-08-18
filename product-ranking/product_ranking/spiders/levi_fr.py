from product_ranking.spiders.levi import LeviProductsSpider


class LeviFRProductsSpider(LeviProductsSpider):
    name = 'levifr_products'
    country = "FR"
    locale = "fr_FR"
