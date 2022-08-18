from search.spiders.amazon_spider import AmazonSpider

class AmazoncoukSpider(AmazonSpider):

    name = "amazoncouk"

    def init_sub(self):
        super(AmazoncoukSpider, self).init_sub()
        self.target_site = "amazoncouk"
        self.domain = "http://www.amazon.co.uk"
