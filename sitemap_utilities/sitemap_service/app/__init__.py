import base64
import codecs
import csv
import json
from multiprocessing.util import register_after_fork
import os
import traceback
import urllib2
import re

from flask import Flask, Response, render_template, request, send_file, url_for, redirect, flash
from flask_login import login_required, current_user
from flask_restful import Resource, Api, abort, reqparse
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from xlrd import open_workbook

app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)
register_after_fork(db, lambda db: db.engine.dispose())

import auth
from models import SitemapRequest, Product, Semrush


@app.route('/', defaults={'request_id': None})
@app.route('/<request_id>')
@login_required
def index(request_id):
    page_reload = False

    try:
        if request_id:
            flash('Click "Browse" to check results and logs after finish')
            sitemap_requests = SitemapRequest.query.filter_by(id=request_id)
            page_reload = True
        else:
            sitemap_requests = SitemapRequest.query.order_by(SitemapRequest.created_at.desc())

        sitemap_requests = sitemap_requests.paginate(per_page=app.config['PAGINATION'], error_out=False)
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        return render_template('index.html', title='Requests', sitemap_requests=sitemap_requests, reload=page_reload)


@app.route('/<request_id>/data')
@login_required
def request_data(request_id):
    try:
        sitemap_request = SitemapRequest.query.filter_by(id=request_id).first()
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        if not sitemap_request:
            abort(404)

        data = sitemap_request.data

        try:
           data = json.dumps(json.loads(data), indent=2)
        except:
            pass

        return render_template('data.html', title='Data', request_id=request_id, data=data)


@app.route('/<request_id>/resources/', defaults={'resource': ''})
@app.route('/<request_id>/resources/<resource>')
@login_required
def request_resources(request_id, resource):
    try:
        sitemap_request = SitemapRequest.query.filter_by(id=request_id).first()
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        if not sitemap_request:
            abort(404)

        resource_path = os.path.join(app.config['SITEMAP_RESOURCES_DIR'], request_id, resource)

        if not os.path.exists(resource_path):
            abort(404)

        if os.path.isfile(resource_path):
            return send_file(resource_path, as_attachment=True)

        resources = []
        files = os.listdir(resource_path)

        for filename in sorted(files):
                file_path = os.path.join(resource_path, filename)

                if os.path.isfile(file_path):
                    resources.append(filename)

        return render_template('resources.html',  title='Resources', request_id=request_id, resources=resources)


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'GET':
        return render_template('create.html', title='Create')

    urls = request.form.get('urls')
    if urls:
        urls = filter(None, urls.replace('\r', '\n').split('\n'))

        try:
            # convert in dict if shelf name exists
            urls = dict(map(lambda x: x.split(',', 1)[::-1], urls))
        except:
            pass
    else:
        urls = []

    urls_file = request.files.get('urls_file')
    if urls_file:
        file_contents = urls_file.read()
        if urls_file.filename.endswith('.xls') or urls_file.filename.endswith('.xlsx'):
            wb = open_workbook(file_contents=file_contents)
            ws = wb.sheet_by_index(0)
            urls = filter(None, (row[0].value for row in ws.get_rows()))
        else:
            if file_contents.startswith(codecs.BOM_UTF8):
                file_contents = file_contents[len(codecs.BOM_UTF8):]
            urls = filter(None, file_contents.replace('\r', '\n').split('\n'))

    upcs = request.form.get('upcs')
    if upcs:
        upcs = filter(None, upcs.replace('\r', '\n').split('\n'))
        upcs = map(lambda x: x[-12].zfill(12), upcs)
    else:
        upcs = []

    asins = request.form.get('asins')
    if asins:
        asins = filter(None, asins.replace('\r', '\n').split('\n'))
    else:
        asins = []

    tcins = request.form.get('tcins')
    if tcins:
        tcins = filter(None, tcins.replace('\r', '\n').split('\n'))
    else:
        tcins = []

    retailer = request.form.get('retailer')
    type = request.form.get('task')

    name = request.form.get('name')

    login = request.form.get('login')
    password = request.form.get('password')
    zip_code = request.form.get('zip_code')
    store = request.form.get('store')
    server = request.form.get('server')

    exclude = request.form.get('exclude')
    exclude = [exclude] if exclude else []

    check_upc = bool(request.form.get('check_upc'))
    check_name = bool(request.form.get('check_name'))

    ignore_cache = bool(request.form.get('ignore_cache'))
    brands_comparison = bool(request.form.get('brands_comparison'))

    search_terms = request.form.get('search_terms')
    if search_terms:
        search_terms = filter(None, map(lambda x: x.strip(), re.sub(r'[\r,]+', '\n', search_terms).split('\n')))
    else:
        search_terms = []

    department = request.form.get('department')

    stores = []
    stores_file = request.files.get('stores_file')
    if stores_file:
        stores_file_lines = stores_file.read().splitlines()
        csv_reader = csv.reader(stores_file_lines[1:], dialect=csv.Sniffer().sniff(stores_file_lines[0]))

        for row in csv_reader:
            if row:
                if len(row) > 1:
                    stores.append({
                        'zip_code': row[0],
                        'store_id': row[1]
                    })
                else:
                    app.logger.error('Wrong stores file format: {}'.format(row))

    brands = request.form.get('brands')
    if brands:
        brands = filter(None, map(lambda x: x.strip(), re.sub(r'[\r,]+', '\n', brands).split('\n')))
    else:
        brands = []

    sizes = request.form.get('sizes')
    if sizes:
        if request.form.get('sizes_variants'):
            sizes_variants = filter(None, map(lambda x: x.strip(), re.sub(r'[\r]+', '\n', sizes).split('\n')))
            sizes = [filter(None, (map(lambda x: x.strip(), variants.split(',')))) for variants in sizes_variants]
        else:
            sizes = filter(None, map(lambda x: x.strip(), re.sub(r'[\r,]+', '\n', sizes).split('\n')))
    else:
        sizes = []

    request_data = {
        'request': {
            'type': type,
            'retailer': retailer,
            'options': {
                'urls': urls,
                'upcs': upcs,
                'asins': asins,
                'tcins': tcins,
                'login': login,
                'password': password,
                'zip_code': zip_code,
                'store': store,
                'server': server,
                'exclude': exclude,
                'check_upc': check_upc,
                'check_name': check_name,
                'ignore_cache': ignore_cache,
                'search_terms': search_terms,
                'department': department,
                'stores': stores,
                'brands': brands,
                'brands_comparison': brands_comparison,
                'sizes': sizes
            }
        }
    }

    try:
        create_request = urllib2.Request(
            url_for('request', _external=True),
            data=json.dumps(request_data),
            headers={
                'Request-Name': name,
                'Content-Type': 'application/json',
                'Authorization': 'Basic {}'.format(
                    base64.b64encode('{}:{}'.format(current_user.name, current_user.password)))
            })

        create_response = json.load(urllib2.urlopen(create_request))

        return redirect(url_for('index', request_id=create_response.get('request_id')))
    except:
        app.logger.error('Create request error: {}'.format(traceback.format_exc()))
        flash('Could not create new request. Check logs')

        return render_template('create.html', title='Create')


@app.route('/url_generator', methods=['GET', 'POST'])
@login_required
def url_generator():
    if request.method == 'GET':
        return render_template('url_generator.html', title='URL Generator')

    retailer = request.form.get('retailer')

    ids = request.form.get('ids')
    if ids:
        ids = filter(None, ids.replace('\r', '\n').split('\n'))
    else:
        ids = []

    urls = []

    for product_id in ids:
        if retailer == 'bestbuy.com':
            urls.append('https://www.bestbuy.com/site/-/{}.p'.format(product_id))

    return render_template('url_generator.html', title='URL Generator', urls=urls)


@app.route('/products', methods=['GET', 'POST'])
@login_required
def show_products():
    try:
        search_filter = get_search_filter()

        if search_filter is not None:
            products = Product.query.filter(search_filter)
        else:
            products = Product.query

        products = products.paginate(per_page=app.config['PAGINATION'], error_out=False)
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        return render_template('products.html', title='Products match', products=products)


@app.route('/export_products', methods=['POST'])
@login_required
def export_products():
    try:
        search_filter = get_search_filter()

        if search_filter is not None:
            products = Product.query.filter(search_filter)
        else:
            products = Product.query

        products = products.all()
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        def csv_data():
            yield ['UPC', 'ASIN', 'Amazon URL', 'Walmart URL', 'Jet URL']

            for product in products:
                yield [product.upc, product.asin, 'https://www.amazon.com/dp/{}'.format(product.asin),
                       product.walmart_url, product.jet_url]

        csv_writer = csv.writer(type('Echo', (object,), {'write': lambda self, x: x})())

        return Response(
            (csv_writer.writerow(row) for row in csv_data()),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=products.csv'}
        )


@app.route('/delete_products', methods=['GET', 'POST'])
@login_required
def delete_products():
    try:
        search_filter = get_search_filter()

        if search_filter is not None:
            Product.query.filter(search_filter).delete(synchronize_session=False)
            db.session.commit()
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        return redirect(url_for('show_products'))


@app.route('/semrush', methods=['GET', 'POST'])
@login_required
def show_semrush():
    try:
        url = request.values.get('url')

        if url:
            semrush = Semrush.query.filter(Semrush.url.like('%{}%'.format(url)))
        else:
            semrush = Semrush.query

        semrush = semrush.paginate(per_page=app.config['PAGINATION'], error_out=False)
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        return render_template('semrush.html', title='SEMrush cache', semrush=semrush)


@app.route('/delete_semrush', methods=['POST'])
@login_required
def delete_semrush():
    try:
        url = request.values.get('url')

        if url:
            semrush = Semrush.query.filter(Semrush.url.like('%{}%'.format(url)))
        else:
            semrush = Semrush.query

        semrush.delete(synchronize_session=False)
        db.session.commit()
    except:
        app.logger.error(traceback.format_exc())
        abort(500, message='Request could not be processed')
    else:
        return redirect(url_for('show_semrush'))


def parse_caids(caids_file):
    caids_csv = csv.reader(caids_file)

    # skip header
    caids_csv.next()

    return [row[0].strip() for row in caids_csv if row]


def get_search_filter():
    product_id = request.values.get('product_id')
    if product_id:
        products = filter(None, map(lambda x: re.sub(r'\W', '', x.strip()), re.split(r'[\n, ]', product_id)))

        upc_filter = map(lambda x: Product.upc.like('%{}%'.format(x)), products)
        asin_filter = map(lambda x: Product.asin.like('%{}%'.format(x)), products)

        search_filter = upc_filter + asin_filter

        return or_(*search_filter)


class RequestListAPI(Resource):

    decorators = [login_required]

    def post(self):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('Request-Name', dest='name', location='headers')
            args = parser.parse_args()

            sitemap_request = SitemapRequest(data=request.data, name=args.name)

            db.session.add(sitemap_request)
            db.session.commit()

            return {
                'status': sitemap_request.state,
                'request_id': sitemap_request.id
            }
        except:
            app.logger.error(traceback.format_exc())
            abort(500, message='Request could not be processed')


class RequestAPI(Resource):

    decorators = [login_required]

    def get(self, request_id):
        app.logger.info('{}: checking status of request'.format(request_id))
        sitemap_request = SitemapRequest.query.filter_by(id=request_id).first()

        if not sitemap_request:
            app.logger.warn('{}: request not found'.format(request_id))
            abort(404,
                  request_id=request_id,
                  status='error',
                  message="Request with id '{}' not found".format(request_id))

        try:
            response = {
                'status': sitemap_request.state,
                'request_id': sitemap_request.id
            }

            log_message = "{}: status '{}'".format(sitemap_request.id, sitemap_request.state)

            if sitemap_request.message:
                response['message'] = sitemap_request.message
                log_message += ", message '{}'".format(sitemap_request.message)

            if sitemap_request.results:
                response['file'] = url_for('request_resources',
                                           request_id=request_id,
                                           resource=sitemap_request.results.name,
                                           _external=True)
                log_message += ", file '{}'".format(sitemap_request.results.name)

            app.logger.info(log_message)

            return response
        except:
            app.logger.error(traceback.format_exc())
            abort(500, message='Request could not be processed')


api = Api(app)
api.add_resource(RequestListAPI, '/request', endpoint='request')
api.add_resource(RequestAPI, '/request/<request_id>')
