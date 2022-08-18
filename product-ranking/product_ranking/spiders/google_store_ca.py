from product_ranking.items import SiteProductItem
from product_ranking.spiders.google_store import GoogleStoreProductsSpider
from spiders_shared_code.google_store_ca_variants import GoogleStoreCaVariants
from product_ranking.spiders import cond_set_value


class GoogleStoreCaProductsSpider(GoogleStoreProductsSpider):
    name = 'google_store_ca_products'
    COUNTRY = {
        'code': 'ca',
        'locale': 'en-CA',
        'currency': 'CAD',
    }

    def _parse_variants(self, response):
        gv = GoogleStoreCaVariants()
        gv.setupSC(response)
        return gv._variants()

    def parse_product(self, response):
        product = super(GoogleStoreCaProductsSpider, self).parse_product(response)
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)
        return product
