# pip install flask-login
# pip install flask

import csv
import json
import os
import random
import re
import string
import tempfile
import traceback
import urllib2

import flask_login
import jinja2
from flask import (Flask, Response, request, render_template, send_file, jsonify)

from auth import user_loader
from converters.amazon_channel import AmazonChannel
from converters.amazon_template_to_json import AmazonTemplateToJSON
from converters.homedepot import HomedepotTemplateGenerator
from converters.product_name import WalmartGrocery, WupcUpc
from converters.homedepotsubmission import HomeDepotProxy
from utils import get_google_mc_approved_brands
from utils import get_mc_api_key

app = Flask(__name__)
CWD = os.path.dirname(os.path.abspath(__file__))

app.secret_key = '7946fe07cc4ef6572c24510e2bfb6c780c9c62e7a82e8a0fmastercategory'

CHECK_CREDENTIALS = False
MC_API_URL = '{server_name}/api/products?api_key={api_key}{filters}' \
             '&product[apply_product_changes]=true'

CONVERT_TYPE_WALMART_GROCERY = 'walmart_grocery'
CONVERT_TYPE_AMAZON_CHANNEL = 'amazon_channel'
CONVERT_TYPE_AMAZON_TEMPLATE_TO_JSON = 'amazon_template_to_json'
CONVERT_TYPE_HOME_DEPOT_SUBMISSION = 'home_depot'
CONVERTER_CONVERT_TYPES = (  # value, text, title (for html select)
    (CONVERT_TYPE_WALMART_GROCERY, 'Walmart Grocery Product Name', ''),
    (
        CONVERT_TYPE_AMAZON_CHANNEL,
        'Amazon Channel (Core vs. Pantry)',
        'Input file should contain a list of Amazon URLs'
    ),
    (CONVERT_TYPE_AMAZON_TEMPLATE_TO_JSON, 'Amazon template to JSON', ''),
    (CONVERT_TYPE_HOME_DEPOT_SUBMISSION, 'Home Depot API Submission', ''),
)

HD_CHANNEL_TEST = 'homedepot-thd-qa'
HD_CHANNEL_PRD = 'home-depot'
HD_CHANNELS = (  # value, text
    (HD_CHANNEL_TEST, HD_CHANNEL_TEST),
    (HD_CHANNEL_PRD, HD_CHANNEL_PRD),
)

login_manager = flask_login.LoginManager()
login_manager.user_callback = user_loader
login_manager.init_app(app)


def run_converter(input_type, output_type, input_file, mapping_file):
    log_fname = tempfile.NamedTemporaryFile(delete=False)
    log_fname.close()
    log_fname = log_fname.name

    converters_dir = os.path.join(CWD, 'converters')

    if not os.path.exists(converters_dir):
        converters_dir = '.'

    cmd = ('python {converters_dir}/main.py --input_type="{input_type}"'
           ' --input_file="{input_file}" --mapping_file="{mapping_file}"'
           ' --output_type="{output_type}" --log_file="{log_file}"')

    cmd_run = cmd.format(converters_dir=converters_dir, log_file=log_fname,
                         input_type=input_type, output_type=output_type,
                         input_file=input_file, mapping_file=mapping_file)

    print('------- Run converter ----------')
    print(cmd_run)
    print('--------------------------------')
    os.system(cmd_run)

    return log_fname


def upload_file_to_our_server(file):
    fname = file.filename.replace('/', '')
    while fname.startswith('.'):
        fname = fname[1:]
    fname2 = ''
    for c in fname:
        if (c in string.ascii_lowercase or c in string.ascii_uppercase
                or c in string.digits or c in ('.', '_', '-')):
            fname2 += c
        else:
            fname2 += '-'
    fname = fname2
    if not os.path.exists(os.path.join(CWD, '_uploads')):
        os.makedirs(os.path.join(CWD, '_uploads'))
    tmp_local_file = os.path.join(CWD, '_uploads', fname)
    if os.path.exists(tmp_local_file):
        while os.path.exists(tmp_local_file):
            f_name, f_ext = tmp_local_file.rsplit('.', 1)
            f_name += str(random.randint(1, 9))
            tmp_local_file = f_name + '.' + f_ext
    file.save(tmp_local_file)
    return os.path.abspath(tmp_local_file)


def parse_log(log_fname):
    if not os.path.exists(log_fname):
        return False, [{'msg': 'Could not find the conversion result.','level': 'ERROR'}], None, ''
    has_error = False
    completed = False
    result_file = None
    file_name = 'result'
    with open(log_fname, 'r') as fh:
        msgs = [json.loads(m.strip()) for m in fh.readlines() if m.strip()]

        for msg in msgs:
            if msg['level'] == 'RESULT_FILE' and os.path.isfile(msg['msg']):
                result_file = msg['msg']
            if msg['level'] == 'FILE_NAME':
                file_name = msg['msg']
            if msg['level'] == 'ERROR':
                has_error = True
            if msg['msg'] == 'Finished':
                completed = True

    is_success = True if not has_error and completed else False

    return is_success, msgs, result_file, file_name


def process_form():
    input_type = request.form.get('input_type', None)
    output_type = request.form.get('output_type', None)
    caids_file = request.files.get('caids_file', None)

    if not input_type:
        return 'Choose input type'
    if not output_type:
        return 'Choose output type'

    if input_type == 'template' and output_type == 'googlemanufacturer' and caids_file:
        server_name = request.form.get('server')
        if not server_name:
            return 'Missing parameter: server. Must be MC server name'
        elif not re.match(r'https?', server_name):
            server_name = 'https://{}.contentanalyticsinc.com'.format(server_name)

        caids = parse_caids(caids_file)

        if len(caids) == 0:
            return 'Empty caids file'

        products = load_products(caids, server_name)

        xml = generate_google_xml(
            products,
            server_name,
            target_client_id=request.form.get('target_client_id', None)
        )

        return True, None, xml, 'google.xml'
    else:
        input_file = request.files.get('input_file', None)
        mapping_file = request.files.get('mapping_file', None)

        if not input_file:
            return 'Choose input file'

        # if not mapping_file:
        #     return 'Choose ID mapping file'

        input_f = upload_file_to_our_server(input_file)
        if mapping_file:
            mapping_f = upload_file_to_our_server(mapping_file)
        else:
            mapping_f = ''

        log_fname = run_converter(input_type=input_type, output_type=output_type,
                                  input_file=input_f, mapping_file=mapping_f)
        success, messages, result_file, file_name = parse_log(log_fname)

        return success, messages, result_file, file_name


@app.route('/converter', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')

    _msgs = process_form()
    if isinstance(_msgs, (list, tuple)):
        success, messages, result_file, file_name = _msgs
    else:
        return _msgs

    if not success:
        result_response = """
            <h2>Status: <b>FAILED</b></h2>
            <h2>Log:</h2>
            <p>{messages}</p>
            <a href='/'>Back</a>
        """.format(messages='<br/>'.join([m.get('msg') for m in messages]))
        return result_response

    if not result_file\
            or not isinstance(result_file, jinja2.environment.TemplateStream) and not os.path.exists(result_file):
        result_response = """
            <h2>Status: <b>FAILED - converted file does not exist</b></h2>
            <h2>Log:</h2>
            <p>{messages}</p>
            <a href='/'>Back</a>
        """.format(messages='<br/>'.join([m.get('msg') for m in messages]))
        return result_response

    try:
        if isinstance(result_file, jinja2.environment.TemplateStream):
            return Response(result_file,
                            mimetype='application/force-download',
                            headers={'Content-Disposition': 'attachment;filename={}'.format(file_name)})
        else:
            return send_file(result_file,
                             mimetype='application/force-download',
                             as_attachment=True,
                             attachment_filename=file_name)
    except:
        result_response = """
            <h2>Status: <b>FAILED - did not find the result file</b></h2>
            <h2>Log:</h2>
            <p>{messages}</p>
            <a href='/'>Back</a>
        """.format(messages='<br/>'.join([m.get('msg') for m in messages]))
        return result_response


@app.route('/converter/api', methods=['GET', 'POST'])
def api():
    if request.method == 'GET':
        return render_template('api.html')

    _msgs = process_form()
    if isinstance(_msgs, (list, tuple)):
        success, messages, result_file, file_name = _msgs
    else:
        return jsonify({'status': 'error', 'message': _msgs}), 400

    if not success:
        return jsonify({
            'status': 'error',
            'message': messages
        }), 400

    if not result_file\
            or not isinstance(result_file, jinja2.environment.TemplateStream) and not os.path.exists(result_file):
        return jsonify({
            'status': 'error',
            'message': 'The converter is not finished successfully.'
        }), 400

    try:
        if isinstance(result_file, jinja2.environment.TemplateStream):
            return Response(result_file,
                            mimetype='application/force-download',
                            headers={'Content-Disposition': 'attachment;filename={}'.format(file_name)})
        else:
            return send_file(result_file,
                             mimetype='application/force-download',
                             as_attachment=True,
                             attachment_filename=file_name)
    except:
        return jsonify({
            'status': 'error',
            'message': 'Could not find the result file.'
        }), 400


@app.route('/convert', methods=['GET', 'POST'])
def convert():
    if request.method == 'GET':
        ctx = {
            'convert_types': CONVERTER_CONVERT_TYPES,
            'hd_convert_type': CONVERT_TYPE_HOME_DEPOT_SUBMISSION,
            'channels': HD_CHANNELS,
        }
        return render_template('convert.html', **ctx)

    input_file = request.files.get('input_file', None)
    if not input_file:
        return jsonify({'status': 'error', 'message': 'Choose input file'}), 400

    output_file = os.path.splitext(input_file.filename)
    input_file = upload_file_to_our_server(input_file)

    input_type = request.form.get('input_type', None)
    if not input_type:
        return jsonify({'status': 'error', 'message': 'Choose input type'}), 400

    if input_type == CONVERT_TYPE_WALMART_GROCERY:
        converter = WalmartGrocery(input_file)
    elif input_type == CONVERT_TYPE_AMAZON_CHANNEL:
        converter = AmazonChannel(input_file)
    elif input_type == CONVERT_TYPE_AMAZON_TEMPLATE_TO_JSON:
        converter = AmazonTemplateToJSON(input_file)
    elif input_type == CONVERT_TYPE_HOME_DEPOT_SUBMISSION:
        channel = request.form.get('channel_id', None)
        if not channel:
            return jsonify({'status': 'error', 'message': 'Home Depot channel is missed'}), 400
        converter = HomeDepotProxy(input_file, channel)
    else:
        return jsonify({'status': 'error', 'message': 'Unknown input type'}), 400

    output_file_ext = converter.output_ext if hasattr(converter, 'output_ext') else output_file[1]
    output_file = '{}_result{}'.format(output_file[0],  output_file_ext)
    return Response(
        converter.convert(),
        mimetype=converter.output_type,
        headers={'Content-Disposition': 'attachment;filename="{}"'.format(output_file)}
    )


@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'GET':
        return render_template('generate.html')

    category_id = request.form.get('category_id', None)
    if not category_id:
        return jsonify({'status': 'error', 'message': 'Missing param: category id'}), 400

    generator = HomedepotTemplateGenerator()

    try:
        template = generator.generate(category_id)

        return send_file(template['content'],
                         as_attachment=True,
                         attachment_filename=template['name'])
    except Exception as e:
        print 'Generator error: {}'.format(traceback.format_exc())

        return jsonify({
            'status': 'error',
            'message': e.message
        }), 500


@app.route('/wupc', methods=['GET', 'POST'])
def convert_upc_to_wupc():
    if request.method == 'GET':
        return render_template('upc_to_wupc_convert.html')

    input_file = request.files.get('input_file', None)
    if not input_file:
        return jsonify({'status': 'error', 'message': 'Choose input file'}), 400

    output_file = os.path.splitext(input_file.filename)
    output_file = '{}_result{}'.format(output_file[0], output_file[1])

    input_file = upload_file_to_our_server(input_file)

    conversion_type = request.form.get('conversion_type', None)
    if not conversion_type:
        return jsonify({'status': 'error', 'message': 'Choose conversion type'}), 400

    if conversion_type == 'upc_to_wupc':
        conversion_type = WupcUpc.UPC_TO_WUPC
    elif conversion_type == 'wupc_to_upc':
        conversion_type = WupcUpc.WUPC_TO_UPC
    else:
        return jsonify({'status': 'error', 'message': 'Unknown conversion type'}), 400

    converter = WupcUpc(input_file, conversion_type)

    return Response(
        converter.convert(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename="{}"'.format(output_file)}
    )


def parse_caids(caids_file):
    caids_csv = csv.reader(caids_file)

    # skip header
    caids_csv.next()

    return filter(None, (row[0].strip() if row else None for row in caids_csv))


def load_products(caids, server_name):
    request_limit = 100

    for i in range(0, len(caids), request_limit):
        filters = reduce(lambda filters, caid: '{}&filter[products][]={}'.format(filters, caid),
                         caids[i:i + request_limit],
                         '')

        url = MC_API_URL.format(
            server_name=server_name,
            api_key=get_mc_api_key(server_name),
            filters=filters
        )

        try:
            print('LOADING PRODUCTS: {}'.format(url))
            res = urllib2.urlopen(url)
        except:
            print(traceback.format_exc())
        else:
            if res.getcode() != 200:
                print('ERROR: response code {}, content: {}'.format(res.getcode(), res.read()))
                print(traceback.format_exc())
            else:
                content = res.read()

                try:
                    data = json.loads(content)
                    for product in data.get('products', []):
                        yield product
                except:
                    print('ERROR: content: {}'.format(content))
                    print(traceback.format_exc())


def generate_google_xml(products, server_name, **kwargs):
    template_loader = jinja2.FileSystemLoader(searchpath=os.path.join(CWD, 'converters', 'templates'))
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template('GoogleManufacturer.html')

    items = get_google_xml_items(products, server_name, **kwargs)

    return template.stream(items=items)


def get_google_xml_items(products, server_name, **kwargs):
    def _retrieve_approved_brands(_customer_id):
        if not _customer_id:
            return {}
        if _customer_id not in approved_brands_cache:
            approved_brands_cache[_customer_id] = get_google_mc_approved_brands(server_name, _customer_id)
        return approved_brands_cache[_customer_id]

    approved_brands_cache = {}
    for product in products:
        item = {
            'id': product.get('id') or '',
            'brand': product.get('brand_attribute') or product.get('brand') or '',
            'title': words_to_abbreviations(product.get('product_name')) or '',
            'gtin': product.get('upc') or '',
            'description': filter_description(product.get('long_description')) or '',
        }

        # if approved brands available we checking brands with it. In other way checking hardcoded values.
        customer_id = product.get('customer_id')
        approved_brands = _retrieve_approved_brands(customer_id)
        if approved_brands:
            if item['brand'] in approved_brands:
                item['brand'] = approved_brands[item['brand']]
        else:
            if item['brand'] == 'Frito Lay Variety Pack':
                item['product_line'] = item['brand']
                item['brand'] = 'Frito Lay'

            if item['brand'] == 'Fisher-Price':
                item['brand'] = 'Fisher Price'

        images = product.get('image_urls')

        if images:
            item['primary_image'] = images[0]
            item['additional_images'] = images[1:]

        item.update(kwargs)

        yield item


def filter_description(description):
    if description is not None:
        # remove <p> tags
        description = re.sub(r'<p>', '', description)
        # content <tag> <tag> </p> -> content. <tag> <tag>
        description = re.sub(r'(\w)\s*((\s*<[^>]+>\s*)+?)\s*</p>', r'\1. \2', description)
        # content </p> -> content.
        description = re.sub(r'(\w)\s*</p>', r'\1. ', description)
        # remove </p> tags
        description = re.sub(r'\s*</p>', r' ', description)

    return description


def words_to_abbreviations(text):
    if text is not None:
        abbreviations = {
            'Fluid': 'Fld',
            'fluid': 'fld',
            'Ounce': 'Oz',
            'ounce': 'oz',
            'Liter': 'Ltr',
            'liter': 'ltr',
            'Pound': 'Lb',
            'pound': 'lb'
        }

        for word, abbr in abbreviations.iteritems():
            text = text.replace(word, abbr)

    return text

if __name__ == '__main__':
    app.run(port=8000, host='127.0.0.1')
