from flask import Flask, jsonify, abort, request, render_template, Response, g
from flask.ext.basicauth import BasicAuth
import random
import urllib2
from lxml import html
from flask.ext.sqlalchemy import SQLAlchemy
import logging
import datetime
from logging import FileHandler
import json
import random

app = Flask(__name__)
app.config['BASIC_AUTH_USERNAME'] = 'test'
app.config['BASIC_AUTH_PASSWORD'] = '632316f5ecdb9bba3b7c55b570911aaf'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///matching_feedback.db'

fh = FileHandler("workbench.log")
fh.setLevel(logging.DEBUG)
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(fh)


basic_auth = BasicAuth(app)

urls = []
MAX_RETRIES = 3

db = SQLAlchemy(app)

class Match(db.Model):
    __tablename__ = 'matches'
    # __table_args__ = (UniqueConstraint('url1', 'url2', name='_urlpair_uc'),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    url1 = db.Column(db.String(100))
    url2 = db.Column(db.String(100))
    product_matches = db.Column(db.Boolean)
    name_matches = db.Column(db.Boolean)
    image_matches = db.Column(db.Boolean)
    manufacturer_matches = db.Column(db.Boolean)
    category_matches = db.Column(db.Boolean)
    seen = db.Column(db.Boolean)

    def __init__(self, url1=None, url2=None, product_matches=None, name_matches=None,\
     image_matches=None, manufacturer_matches=None, category_matches=None, seen=None):
        self.url1 = url1
        self.url2 = url2
        self.product_matches = product_matches
        self.name_matches = name_matches
        self.image_matches = image_matches
        self.manufacturer_matches = manufacturer_matches
        self.category_matches = category_matches
        self.seen = seen

    def __repr__(self):
        return str(self.__dict__)

    def set_values(self, product_matches=None, name_matches=None,\
     image_matches=None, manufacturer_matches=None, category_matches=None, seen=None):
        self.product_matches = product_matches
        self.name_matches = name_matches
        self.image_matches = image_matches
        self.manufacturer_matches = manufacturer_matches
        self.category_matches = category_matches
        self.seen = seen
        print "SET VALUES", self

def import_matches_from_file(matches_path = "/home/ana/code/tmtext/data/opd_round3/walmart_amazon_28.08_matches.csv"):
    global urls
    with open(matches_path) as f:
        for line in f:
            try:
                (url1, url2) = line.split(",")
            except:
                # ignore no matches
                continue
            # strip part after ?
            url1 = clean_url(url1)
            url2 = clean_url(url2)
            urls.append((url1, url2))

def clean_url(url):
    return url.split("?")[0]

def import_matches_from_DB():
    '''Return all unseen matches from DB
    '''
    matches = Match.query.filter_by(product_matches=None).all()
    urls = []
    for match in matches:
        url1 = clean_url(match.url1)
        url2 = clean_url(match.url2)
        urls.append((url1, url2))

def export_matches_DB(matches_path = "/home/ana/code/tmtext/data/opd_round3/walmart_amazon_28.08_matches.csv"):
    with open(matches_path) as f:
        for line in f:
            try:
                (url1, url2) = line.split(",")
            except:
                # ignore no matches
                continue
            # strip part after ?
            url1 = clean_url(url1)
            url2 = clean_url(url2)

            match = Match.query.filter_by(url1=url1, url2=url2).first()
            if not match:
                match = Match(url1=url1, url2=url2)
                db.session.add(match)
        db.session.commit()


def get_unseen_match():
    '''Return random unseen match from DB
    '''
    matches = Match.query.filter_by(product_matches=None).all()
    if not matches:
        return None
    match = random.choice(matches)
    url1 = clean_url(match.url1)
    url2 = clean_url(match.url2)
    return (url1, url2)

def init():

    db.create_all()
    db.session.commit()
    # if there are no unseen matches in DB, get them from file
    match = get_unseen_match()
    if not match:
        export_matches_DB()
    match = get_unseen_match()
    if not match:
        import_matches_from_file()

init()

@app.route('/workbench', methods = ['GET', 'POST'])
@basic_auth.required
def display_match():
    # store form data
    if request.form:
        url1 = request.form['url1']
        url2 = request.form['url2']
        store_feedback(request.form)

    global urls
    if urls:
        matches = urls.pop()
    else:
        matches = get_unseen_match()
    if not matches and not urls:
        return render_template('gameover.html')
        app.logger.error("No more matches to show")
    return render_template('workbench.html', matches=matches)

# use this for loading iframes on sites that don't permit iframes?
@app.route('/page/<path:url>', methods = ['GET'])
def serve_page(url):
    req = urllib2.Request(url)
    req.add_header('User Agent', 'Mozilla')
    
    try:    
        resp = urllib2.urlopen(req)
    except:
        resp = None

    # retry if failed
    retries = 0
    while (not resp or resp.code != 200) and retries < MAX_RETRIES:
        try:
            resp = urllib2.urlopen(req)
        except:
            resp = None
        retries += 1
        app.logger.warning("Retrying to get page " + url + "\n")

    if not resp:
        app.logger.error("Failed to get page " + url + "\n")

    body = remove_scripts(resp.read())

    response = Response(body)
    return response

def remove_scripts(body):
    '''Remove <script> tags from page source.
    This will prevent additional js code and AJAX requests
    to execute, making it faster to load the page in the iframe
    '''
    root = html.fromstring(body).getroottree()
    for element in root.iter("script"):
        element.drop_tree()
    return html.tostring(root)


def store_feedback(features_dict):
    '''
    :param features_dict: dict of features and yes/no (matches or not) for each
    '''

    keys2cols = {
    'url1' : 'url1',
    'url2' : 'url2',
    'product': 'product_matches',
    'name' : 'name_matches', 
    'image' : 'image_matches',
    'manufacturer' : 'manufacturer_matches',
    'category' : 'category_matches'
    }
    columns = []
    values = {}
    for key in keys2cols:
        columns.append(keys2cols[key])
        if key not in features_dict:
            values[keys2cols[key]] = None
        else:
            if key not in ['url1', 'url2']:
                values[keys2cols[key]] = True if features_dict[key]=='yes' else False
            else:
                values[keys2cols[key]] = features_dict[key]

    # if there is not already a match for these urls, insert it
    # if there is already a match but with no feedback, update it
    match = Match.query.filter_by(url1=features_dict['url1'], url2=features_dict['url2']).first() 
    if not match:
        match = Match(**values)
        db.session.add(match)
        db.session.commit()
    else:
        if match.product_matches is not None:
            app.logger.warning("Match was already in DB " + str(match) + "\n")
        else:
            del values['url1']
            del values['url2']
            match.set_values(**values)
            db.session.add(match)
            db.session.commit()

@app.after_request
def post_request_logging(response):

    app.logger.info(json.dumps({
        "date" : datetime.datetime.today().ctime(),
        "remote_addr" : request.remote_addr,
        "request_method" : request.method,
        "request_url" : request.url,
        "response_status_code" : str(response.status_code),
        "request_headers" : ', '.join([': '.join(x) for x in request.headers]),
        "form_data" : request.form
        })
    )

    return response

if __name__ == '__main__':
    app.run(port = 8080, threaded = True)