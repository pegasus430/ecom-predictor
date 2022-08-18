from product_ranking.items import BuyerReviews
from product_ranking.spiders import cond_set_value


def populate_reviews(response, reviews):
    """ Populate `buyer_reviews` from list of user ratings as floats """
    if reviews:
        by_star = {rating: reviews.count(rating) for rating in reviews}
        reviews = BuyerReviews(num_of_reviews=len(reviews),
                               average_rating=sum(reviews) / len(reviews),
                               rating_by_star=by_star)
        cond_set_value(response.meta['product'], 'buyer_reviews', reviews)


def populate_reviews_from_regexp(regexp, response, string_):
    """ Populate `buyer_reviews` from regular expression.

     The regular expression should return a list of digits.
     """
    reviews = map(float, regexp.findall(string_))
    populate_reviews(response, reviews)