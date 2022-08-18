import json
import traceback

from scrapy import log
from scrapy.log import WARNING

from product_ranking.items import BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE

def parse_powerreviews_buyer_reviews(response):
    try:
        review_data = json.loads(response.body_as_unicode()).get('results')[0]
        num_of_reviews = review_data.get(
            'metrics',
            review_data.get('rollup', {})
        ).get('review_count', 0)

        average_rating = review_data.get(
            'metrics',
            review_data.get('rollup', {})
        ).get('average_rating', 0)

        rating_by_star = {
            str(star): value for star, value in enumerate(review_data.get('rollup', {}).get('rating_histogram', []), 1)
            }
    except:
        log.msg('Can not extract json data: {}'.format(traceback.format_exc()), WARNING)
        num_of_reviews, average_rating, rating_by_star = ZERO_REVIEWS_VALUE
    finally:
        buyer_reviews = {
            'rating_by_star': rating_by_star,
            'average_rating': average_rating,
            'num_of_reviews': num_of_reviews
        }
        return BuyerReviews(**buyer_reviews)
