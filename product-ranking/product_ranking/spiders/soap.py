from scrapy.log import ERROR

from product_ranking.quidsi_base_class import QuidsiBaseProductsSpider
from product_ranking.spiders import FormatterWithDefaults


class SoapProductSpider(QuidsiBaseProductsSpider):
    name = 'soap_products'
    allowed_domains = ["soap.com"]

    SEARCH_URL = 'https://www.soap.com/buy?s={search_term}' \
                 '&ref=srbr_so_unav&st={sort_mode}'
    REVIEWS_URL = 'https://www.soap.com/amazon_reviews/{prodpath}/' \
                  'mosthelpful_Default.html'

    SORT_MODES = {
        'relevance': "Relevance",
        'highestrating': "MergedRating%20(Descending)",
        'pricelh': "Price%20(Ascending)",
        'pricehl': "Price%20(Descending)",
        'nameaz': "Name%20(Ascending)",
        'nameza': "Name%20(Descending)",
        'bestselling': "Bestselling%20(Descending)",
        'newest': "New%20(Descending)",
    }

    def __init__(self, sort_mode='relevance', *args, **kwargs):
        if sort_mode.lower() not in self.SORT_MODES:
            self.log('{} not in SORT_MODES'.format(sort_mode), ERROR)
            sort_mode = 'relevance'

        super(SoapProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                sort_mode=self.SORT_MODES[sort_mode.lower()]
            ),
            *args, **kwargs)
