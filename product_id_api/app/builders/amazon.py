from . import Builder


class AmazonBuilder(Builder):
    retailer = 'amazon'

    @staticmethod
    def build_url(asin):
        return 'https://www.amazon.com/dp/{}'.format(asin)
