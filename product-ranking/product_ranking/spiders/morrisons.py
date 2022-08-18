# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals

from product_ranking.spiders.groceries_morrisons import GroceriesMorrisonsProductsSpider


class MorrisonsProductsSpider(GroceriesMorrisonsProductsSpider):
    # Placeholder duplicate of groceries.morrisons, morrisons.com redirects to groceries
    name = 'morrisons_products'

    def __init__(self, *args, **kwargs):
        super(MorrisonsProductsSpider, self).__init__(
            *args,
            **kwargs)
