from product_ranking.quidsi_base_class import QuidsiBaseProductsSpider


class WagProductsSpider(QuidsiBaseProductsSpider):
    name = 'wag_products'
    allowed_domains = ['wag.com', 'amazon.com']

    SEARCH_URL = ("https://www.wag.com/search/{search_term}?s={search_term}"
                  "&ref=srbr_wa_unav#fromSearch=Y")
    REVIEWS_URL = 'https://www.wag.com/amazon_reviews/{prodpath}/' \
                  'mosthelpful_Default.html'

    def __init__(self, *args, **kwargs):
        super(WagProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args, **kwargs)
