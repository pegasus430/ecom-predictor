import re
import csv
import logging
import argparse
import requests
import urlparse
import zipfile
import io
import json
import time
import os
from functools import wraps
from datetime import datetime
from subprocess import call

from flask import Flask, render_template_string, send_file, request, Response

app = Flask(__name__)
app.config['LOG_LEVEL'] = logging.DEBUG

API_URL_TEMPLATE = 'http://redsky.target.com/v1/plp/search?count=24&' \
                   'offset={offset}&' \
                   'category={category_id}&' \
                   'faceted_value={filter_id}'

SHELF_TO_PRODUCTS_UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Target.com shelf to product urls converter</title>
</head>
<body>
    <form action="/" enctype="multipart/form-data" method="post">
        <p>
            Select CSV file with shelf urls<input type="file" name="shelf_urls">
        </p>
        <input type="submit" value="Submit">
    </form>
</body>
</html>
"""

SITEMAP_SPIDER_UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Target.com sitemap spider</title>
</head>
<body>
    <form action="/sitemap" enctype="multipart/form-data" method="post">
        <p>
            Select website: <select><option value="target" selected>Target.com</option></select>
        </p>
        <p>
            <input type="radio" name="url_type" value="shelf" checked="checked">Shelf page URLs<br>
            <input type="radio" name="url_type" value="item">Item page URLs<br>
            <input type="radio" name="url_type" value="all">All URLs
        </p>
        <input type="submit" value="Download"> and be patient
    </form>
</body>
</html>
"""


def check_auth(username, password):
    return username == 'admin' and password == 'p38YuqNm(t58X8PaV45%'


def authenticate():
    return Response('Login Failed', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/', methods=['GET', 'POST'])
@requires_auth
def index():
    shelf_urls_file = request.files.get('shelf_urls')

    if shelf_urls_file:
        setup_logger(app.logger)
        zipped_buf = process_shelf_urls(shelf_urls_file, app.logger)

        return send_file(zipped_buf, as_attachment=True, attachment_filename='target_product_urls.zip')

    return render_template_string(SHELF_TO_PRODUCTS_UI_TEMPLATE)


@app.route('/sitemap', methods=['GET', 'POST'])
@requires_auth
def sitemap():
    url_type = request.form.get('url_type')

    if url_type is not None:
        output_file = '/tmp/{}_target_sitemap.csv'.format(datetime.now().strftime('%Y%m%d%H%M%S'))

        if url_type == 'shelf':
            # increase speed
            sitemap_url = 'http://www.target.com/c/sitemap_001.xml.gz'
        else:
            sitemap_url = 'http://www.target.com/sitemap_index.xml.gz'

        call(['python', 'sitemap_to_csv.py', sitemap_url, '-o', output_file])

        output_file = filter_urls(output_file, url_type)

        return send_file(output_file, as_attachment=True)

    return render_template_string(SITEMAP_SPIDER_UI_TEMPLATE)


def filter_urls(input_file, url_type):
    output_file = os.path.splitext(input_file)
    output_file = output_file[0] + '_' + url_type + output_file[1]

    with open(input_file, 'rb') as in_f:
        input_csv = csv.reader(in_f)
        headers = next(input_csv, None)

        with open(output_file, 'wb') as out_f:
            output_csv = csv.writer(out_f)

            if headers:
                output_csv.writerow(headers)

                for row in input_csv:
                    url = row[0]

                    if url_type == 'shelf' and 'target.com/c/' in url\
                            or url_type == 'item' and 'target.com/p/' in url\
                            or url_type == 'all':
                        output_csv.writerow(row)

    os.remove(input_file)

    return output_file


def process_shelf_urls(shelf_urls_file, logger):
    csv_reader = csv.reader(shelf_urls_file)

    results = {}

    for row in csv_reader:
        shelf_url = row[0].strip()

        if shelf_url and shelf_url.lower() != 'url':
            logger.info('Processing shelf url: {}'.format(shelf_url))

            category = re.search(r'/c/([^/]+)/-/N-([a-z0-9]+)(?:Z([a-z0-9Z]+))?', shelf_url)
            if category:
                category_name = re.sub(r'-', '_', category.group(1))
                category_id = category.group(2)
                filter_id = category.group(3) or ''

                product_urls = export_product_urls(category_id, filter_id, logger)
                if product_urls:
                    filename = '{}_{}'.format(category_name, filter_id) if filter_id else category_name
                    results[filename] = product_urls
            else:
                logger.error('Wrong url format: {}'.format(shelf_url))

    return zip_results(results)


def zip_results(results):
    zipped_buf = io.BytesIO()

    with zipfile.ZipFile(zipped_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        for category_name, product_urls in results.iteritems():
            zip_file.writestr('{}.csv'.format(category_name), 'url\n' + '\n'.join(product_urls))

    zipped_buf.seek(0)

    return zipped_buf


def export_product_urls(category_id, filter_id, logger):
    product_urls = []
    offset = 0
    max_retry_count = 10
    retry_count = 0

    api_url = API_URL_TEMPLATE.format(offset=offset,
                                      category_id=category_id,
                                      filter_id=filter_id)

    while True:
        response = None

        try:
            logger.debug('Request API: {}'.format(api_url))
            response = requests.get(api_url, headers={'User-Agent': ''})
            response.raise_for_status()

            search_response = response.json().get('search_response')

            if search_response:
                for item in search_response.get('items', {}).get('Item', []):
                    url = item.get('url')
                    if url:
                        product_urls.append(urlparse.urljoin('http://www.target.com', url))
                    else:
                        logger.warn('Item has not url field: {}'.format(json.dumps(item, indent=2)))

                meta_data = search_response.get('metaData', [])
                meta_data = dict((data.get('name'), data.get('value')) for data in meta_data)

                if int(meta_data.get('currentPage', 0)) < int(meta_data.get('totalPages', 0)):
                    offset += int(meta_data.get('count', 24))
                    api_url = API_URL_TEMPLATE.format(offset=offset,
                                                      category_id=category_id,
                                                      filter_id=filter_id)
                    continue

            break
        except Exception as e:
            logger.error('{}, response {}: {}'.format(e,
                                                      getattr(response, 'status_code', None),
                                                      getattr(response, 'content', None)))
            if retry_count < max_retry_count:
                retry_count += 1
                time.sleep(1)
                logger.error('Retry: {}'.format(api_url))
            else:
                logger.error('Max retry times reached: {}'.format(api_url))
                break

    return product_urls


def setup_logger(logger, log_level=logging.DEBUG, path=None):
    """
    Setup logger formats and handlers

    :param logger: logger
    :param log_level: logging level
    :param path: log file path
    :return:
    """

    logger.setLevel(log_level)

    log_format = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
    log_format.datefmt = '%Y-%m-%d %H:%M:%S'

    log_stdout = logging.StreamHandler()
    log_stdout.setFormatter(log_format)
    log_stdout.setLevel(log_level)
    logger.addHandler(log_stdout)

    if path:
        log_file = logging.FileHandler(path)
        log_file.setFormatter(log_format)
        log_file.setLevel(log_level)
        logger.addHandler(log_file)


def get_args():
    """
    Parse command line arguments

    :return: command line arguments
    """

    parser = argparse.ArgumentParser(description='Target. Convert shelf page in product urls')

    parser.add_argument('-i', '--input',
                        help='CSV file with shelf urls')

    parser.add_argument('-o', '--output',
                        default='target_product_urls.zip',
                        help='Output filename')

    parser.add_argument('-s', '--service',
                        action='store_true',
                        help='Run as web service')

    parser.add_argument('-p', '--port',
                        default=8080,
                        help='Port for web service')

    parser.add_argument('-l', '--log',
                        default='target_shelf_service.log',
                        help='Log file path')

    return parser.parse_args()


if __name__ == '__main__':

    args = get_args()

    if args.service:
        app.run('0.0.0.0', port=args.port)
    else:
        logger = logging.getLogger(__name__)
        setup_logger(logger, path=args.log)

        with open(args.input) as shelf_urls_file:
            zipped_buf = process_shelf_urls(shelf_urls_file, logger)

            with open(args.output, 'wb') as output_file:
                output_file.write(zipped_buf.read())
