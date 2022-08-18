import logging
import traceback

from pymongo import ASCENDING
from pymongo import DESCENDING
from pymongo.errors import AutoReconnect
from pymongo.errors import OperationFailure

from app import app
from app.database import init
from app.spiders import load_spiders


db = init(app)
spiders = load_spiders(app.config['SPIDERS_PACKAGE'])

logging.basicConfig(format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

for retailer in spiders:
    logging.info('Retailer: {}'.format(retailer))
    try:
        db['words_%s' % retailer].drop_index([('_id.product_id', ASCENDING), ('value', DESCENDING)])
    except OperationFailure:
        pass
    spider = spiders[retailer]('', '.', db)
    for product_id in db[retailer].distinct('product_id'):
        for i in range(3):
            logging.info('Updating words collection for {} {}'.format(retailer, product_id))
            try:
                spider.update_words_collection(product_id, True)
                break
            except AutoReconnect:
                if i == 2:
                    raise
                logging.error('Connection error: {}'.format(traceback.format_exc()))
logging.info('Done')
