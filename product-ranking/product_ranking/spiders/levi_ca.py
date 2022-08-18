from __future__ import absolute_import, division, unicode_literals

from product_ranking.spiders.levi import LeviProductsSpider


class LeviCAProductsSpider(LeviProductsSpider):
    name = 'levica_products'
    country = "CA"
    locale = "en_CA"
