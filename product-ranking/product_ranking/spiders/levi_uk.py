from product_ranking.spiders.levi  import LeviProductsSpider


class LeviUKProductsSpider(LeviProductsSpider):
    name = 'leviuk_products'
    country = "GB"
    locale = "en_GB"

