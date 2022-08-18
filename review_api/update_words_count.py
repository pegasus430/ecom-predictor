import logging

from pymongo import ASCENDING
from pymongo.errors import OperationFailure

from app import app
from app.database import init
from app.spiders import load_spiders


db = init(app)
spiders = load_spiders(app.config['SPIDERS_PACKAGE'])

logging.basicConfig(format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
                    datefmt = '%Y-%m-%d %H:%M:%S', level=logging.INFO)

for retailer in spiders:
    logging.info('Retailer: {}'.format(retailer))
    try:
        db[retailer].drop_index([('product_id', ASCENDING)])
    except OperationFailure:
        pass
    spider = spiders[retailer]('', '.', db)
    product_id = None
    for review in db[retailer].find().sort('product_id'):
        if product_id != review.get('product_id'):
            product_id = review.get('product_id')
            logging.info('Updating words count for {} {}'.format(retailer, product_id))
        spider._update_words_count(review)
        db[retailer].update_one({'_id': review['_id']}, {'$set': {'words': review['words']}})
logging.info('Done')
