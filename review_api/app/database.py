from pymongo import MongoClient, ASCENDING, DESCENDING

from spiders import load_spiders


def init(app):
    db = MongoClient(app.config['DATABASE_URI'], connect=False)[app.config['DATABASE_NAME']]

    alerts = db['alerts']
    alerts.create_index([('retailer', ASCENDING), ('product_id', ASCENDING)])

    tasks = db['tasks']
    tasks.create_index([('retailer', ASCENDING), ('product_id', ASCENDING)])
    tasks.create_index([('group_id', ASCENDING)])

    daily_tasks = db['daily_tasks']
    daily_tasks.create_index([('retailer', ASCENDING), ('product_id', ASCENDING), ('last_run_at', ASCENDING)])
    daily_tasks.create_index([('group_id', ASCENDING)])

    comments_update = db['comments_update']
    comments_update.create_index([('retailer', ASCENDING), ('product_id', ASCENDING)])

    spiders = load_spiders(app.config['SPIDERS_PACKAGE'])

    for spider in spiders.values():
        collection = db[spider.retailer]
        collection.create_index([('date', DESCENDING)])
        collection.create_index([('product_id', ASCENDING), ('date', DESCENDING)])
        collection.create_index([('rating', ASCENDING)])
        words_collection = db['words_%s' % spider.retailer]
        words_collection.create_index([('_id.product_id', ASCENDING), ('_id.type', ASCENDING), ('_id.date', ASCENDING)])

    return db
