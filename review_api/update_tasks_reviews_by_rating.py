import logging

from pymongo import DESCENDING

from app import app
from app.database import init
from app.spiders import load_spiders


db = init(app)
spiders = load_spiders(app.config['SPIDERS_PACKAGE'])

logging.basicConfig(format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

for retailer in spiders:
    logging.info('Retailer: {}'.format(retailer))
    spider = spiders[retailer]('', '.', db)
    for product_id in db[retailer].distinct('product_id'):
        logging.info('Updating reviews_by_rating for {} {}'.format(retailer, product_id))
        task = db.tasks.find_one({'retailer': retailer, 'product_id': product_id}, sort=[('_id', DESCENDING)])
        if task and task.get('reviews'):
            logging.info('{} new reviews'.format(task['reviews']))
            reviews_by_rating = {str(rating['_id']): rating['count'] for rating in db[retailer].aggregate([
                {'$match': {'product_id': product_id}},
                {'$sort': {'date': -1}},
                {'$limit': task['reviews']},
                {'$group': {'_id': '$rating', 'count': {'$sum': 1}}},
            ])}
            db.tasks.update_one({'_id': task['_id']}, {'$set': {'reviews_by_rating': reviews_by_rating}})
logging.info('Done')
