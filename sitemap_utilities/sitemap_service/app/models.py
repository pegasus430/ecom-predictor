from app import db
from datetime import datetime


class SitemapRequest(db.Model):
    STATE_RECEIVED = 'received'
    STATE_PROCESSING = 'processing'
    STATE_READY = 'ready'
    STATE_ERROR = 'error'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    state = db.Column(db.Enum(STATE_RECEIVED, STATE_PROCESSING, STATE_READY, STATE_ERROR, name='states'),
                      nullable=False, default=STATE_RECEIVED)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    data = db.Column(db.Text, nullable=False)
    message = db.Column(db.Text, nullable=True)
    name = db.Column(db.String(32), nullable=True)

    def __init__(self, data, name=None):
        self.data = data
        self.name = name


class SitemapResults(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    request_id = db.Column(db.Integer, db.ForeignKey('sitemap_request.id'), index=True, nullable=False)
    request = db.relationship('SitemapRequest', backref=db.backref('results', uselist=False))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    name = db.Column(db.String(1024), nullable=False)

    def __init__(self, name):
        self.name = name


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upc = db.Column(db.String(256), nullable=True)
    asin = db.Column(db.String(256), nullable=True)

    walmart_url = db.Column(db.String(1024), nullable=True)
    jet_url = db.Column(db.String(1024), nullable=True)

    def __repr__(self):
        return 'UPC: {upc}, ASIN: {asin}'.format(
            upc=self.upc,
            asin=self.asin
        )


class Semrush(db.Model):
    url = db.Column(db.String(1024), primary_key=True)
    seo_url = db.Column(db.String(1024), nullable=True)
    url_organic = db.Column(db.Text, nullable=True)
    url_organic_date = db.Column(db.Date, nullable=True)
    backlinks_overview = db.Column(db.Text, nullable=True)
    backlinks_overview_date = db.Column(db.Date, nullable=True)


db.create_all()
