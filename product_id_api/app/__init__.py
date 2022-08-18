import traceback
import socket

from datetime import datetime
from StringIO import StringIO
from builders import load_builders
from reader import FileReader

from flask import Flask, render_template, request, send_file, flash
from flask_restful import Resource, Api, abort, reqparse
from flask_sqlalchemy import SQLAlchemy, inspect

app = Flask(__name__)
app.config.from_object('config')

db = SQLAlchemy(app)

from models import Product


class UrlBuilderAPI(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('retailer', required=True)
        parser.add_argument('retailer_id', required=True)
        args = parser.parse_args()

        builder_class = load_builders(app.config['BUILDERS_PACKAGE']).get(args['retailer'])
        if not builder_class:
            abort(400, message='URL builder for retailer {} does not exist'.format(args['retailer']))

        return {'url': builder_class.build_url(args['retailer_id'])}


class UpcAPI(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('id', required=True)
        parser.add_argument('id_value', required=True)
        args = parser.parse_args()

        web_ids = get_web_ids()

        if args['id'] not in web_ids.keys():
            abort(400, message='Not supporting id: {}'.format(args['id']))

        web_id_value = web_ids[args['id']].query.filter_by(value=args['id_value']).all()

        if not web_id_value:
            abort(404, message='Value {} for id {} not found'.format(args['id_value'], args['id']))

        result = map(lambda x: {'upc': x.product.upc}, web_id_value)

        return result[0] if len(result) == 1 else result


class WebIdAPI(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('input_id', required=True)
        parser.add_argument('input_id_value', required=True)
        parser.add_argument('return_id', required=True)
        args = parser.parse_args()

        web_ids = get_web_ids()

        if args['input_id'] not in ['upc'] + web_ids.keys():
            abort(400, message='Not supporting input_id: {}'.format(args['input_id']))

        if args['return_id'] not in ['upc'] + web_ids.keys():
            abort(400, message='Not supporting return_id: {}'.format(args['return_id']))

        if args['input_id'] == 'upc':
            products = Product.query.filter_by(upc=args['input_id_value']).all()

            if not products:
                abort(404, message='Value {} for id {} not found'.format(args['input_id_value'], args['input_id']))
        else:
            web_id_value = web_ids[args['input_id']].query.filter_by(value=args['input_id_value']).all()

            if not web_id_value:
                abort(404, message='Value {} for id {} not found'.format(args['input_id_value'], args['input_id']))

            products = map(lambda x: x.product, web_id_value)

        result = map(lambda x: {args['return_id']: str(getattr(x, args['return_id'], ''))}, products)

        return result[0] if len(result) == 1 else result


class WebIdsAPI(Resource):

    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('input_id', required=True)
        parser.add_argument('input_id_value', required=True)
        args = parser.parse_args()

        web_ids = get_web_ids()

        if args['input_id'] not in ['upc'] + web_ids.keys():
            abort(400, message='Not supporting input_id: {}'.format(args['input_id']))

        if args['input_id'] == 'upc':
            products = Product.query.filter_by(upc=args['input_id_value']).all()

            if not products:
                abort(404, message='Value {} for id {} not found'.format(args['input_id_value'], args['input_id']))
        else:
            web_id_value = web_ids[args['input_id']].query.filter_by(value=args['input_id_value']).all()

            if not web_id_value:
                abort(404, message='Value {} for id {} not found'.format(args['input_id_value'], args['input_id']))

            products = map(lambda x: x.product, web_id_value)

        result = []

        for product in products:
            return_ids = {'upc': product.upc}

            for web_id in web_ids.keys():
                return_ids[web_id] = str(getattr(product, web_id, ''))

            result.append(return_ids)

        return result[0] if len(result) == 1 else result


def get_web_ids():
    relationships = inspect(Product).relationships

    return dict(map(lambda x: (str(x).split('.')[-1], x.mapper.class_), relationships))


def get_server():
    try:
        server = socket.gethostbyaddr(request.remote_addr)[0]
    except:
        server = 'Unknown server'

    return server


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    web_ids = get_web_ids()
    web_ids_sorted = ['upc'] + sorted(web_ids.keys())

    if request.values.get('sample') is not None:
        sample = StringIO(','.join(web_ids_sorted) + '\n')

        return send_file(sample, as_attachment=True, attachment_filename='sample.csv')

    if request.method == 'POST':
        input_file = request.files.get('input_file')

        if input_file:
            try:
                for index, new_product in enumerate(FileReader.read(input_file), 1):
                    upc = new_product.get('upc')

                    if not upc:
                        message = 'Skip. There is not UPC in product #{}: {}'.format(index, new_product)
                        flash(message)
                        app.logger.warn(message)

                        continue

                    product = Product.query.filter_by(upc=upc).first()

                    if not product:
                        product = Product(upc=upc)
                        db.session.add(product)
                    else:
                        product.updated_at = datetime.now()
                        product.updated_by = get_server()

                    for web_id, web_id_class in web_ids.iteritems():
                        new_value = new_product.get(web_id, '')
                        web_id_value = getattr(product, web_id, None)

                        if not web_id_value:
                            web_id_value = web_id_class(value=new_value)
                            web_id_value.product = product
                            db.session.add(web_id_value)
                        else:
                            web_id_value.value = new_value

                db.session.commit()

            except Exception as e:
                app.logger.error(traceback.format_exc())
                flash(e.message)
            else:
                flash('File is uploaded')
        else:
            flash('Please select file for upload')

    return render_template('upload.html', title='Upload UI', web_ids=web_ids_sorted)

api = Api(app)
api.add_resource(UrlBuilderAPI, '/url')
api.add_resource(UpcAPI, '/upc')
api.add_resource(WebIdAPI, '/id')
api.add_resource(WebIdsAPI, '/ids')
