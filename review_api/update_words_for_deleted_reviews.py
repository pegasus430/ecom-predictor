import logging
import traceback

from pymongo.errors import AutoReconnect

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
    for product_id in db['words_%s' % retailer].distinct('_id.product_id'):
        for i in range(3):
            logging.info('Checking {} {}'.format(retailer, product_id))
            try:
                if not db[retailer].find_one({'product_id': product_id}):
                    logging.info('Deleting orphaned words collection for {} {}'.format(retailer, product_id))
                    db['words_%s' % retailer].delete_many({'_id.product_id': product_id})
                break
            except AutoReconnect:
                if i == 2:
                    raise
                logging.error('Connection error: {}'.format(traceback.format_exc()))
logging.info('Done')
