# -*- coding: utf-8 -*-

from product_ranking.spiders.asda import AsdaProductsSpider


class GroceriesAsdaProductsSpider(AsdaProductsSpider):
    """ Derived from AsdaProductsSpider

        All things will be considered on Parent class
        Dummy class which is duplicated for now
    """
    name = 'groceries_asda_products'
    allowed_domains = ["groceries.asda.com"]

    def __init__(self, *args, **kwargs):
        super(GroceriesAsdaProductsSpider, self).__init__(
            *args, **kwargs)