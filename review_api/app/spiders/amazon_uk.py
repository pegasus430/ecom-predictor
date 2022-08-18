from datetime import datetime

from amazon import AmazonReviewSpider


class AmazonUkReviewSpider(AmazonReviewSpider):

    retailer = 'amazon_uk'

    host = 'www.amazon.co.uk'

    def _parse_date(self, review_html):
        date = review_html.xpath(".//*[@data-hook='review-date']/text()")
        if date:
            return datetime.strptime(date[0], 'on %d %B %Y')
