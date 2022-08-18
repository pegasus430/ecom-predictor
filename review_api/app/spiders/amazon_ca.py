from amazon import AmazonReviewSpider


class AmazonCaReviewSpider(AmazonReviewSpider):

    retailer = 'amazon_ca'

    host = 'www.amazon.ca'
