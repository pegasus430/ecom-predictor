from product_ranking.spiders.vons import VonsProductsSpider


class SafeWayProductsSpider(VonsProductsSpider):

    name = 'safeway_products'

    zip = '95811'

    allowed_domains = ["www.safeway.com", "shop.safeway.com", "shop.vons.com", "safeway.com"]
