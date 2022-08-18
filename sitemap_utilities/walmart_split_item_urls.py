import argparse
import logging
import os
import re
import requests
import csv
import multiprocessing as mp
import zipfile
import traceback
import time
import shutil

logger = logging.getLogger(__name__)


def get_args():
    """
    Parse command line arguments

    :return: command line arguments
    """

    parser = argparse.ArgumentParser(description='Split item urls')

    parser.add_argument('items', help='CSV or ZIP file with item urls')

    parser.add_argument('-t', '--threads',
                        type=int,
                        default=50,
                        help='Number of threads')

    parser.add_argument('-l', '--log',
                        default='walmart_split_item_urls.log',
                        help='Log file path')

    parser.add_argument('-o', '--output',
                        help='Output dir')

    return parser.parse_args()


def setup_logger(log_level=logging.DEBUG, path=None):
    """
    Setup logger formats and handlers

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


def parse_item(tasks, output):
    api_url = 'https://www.walmart.com/terra-firma/item/{item_id}'

    session = requests.Session()
    counter = 0

    for item_url in iter(tasks.get, 'STOP'):
        item_id = item_url.split('/')[-1]

        url = api_url.format(item_id=item_id)

        department = None
        store = None

        for i in range(5):
            try:
                response = session.get(url)
                response.raise_for_status()

                data = response.json()

                department = parse_department(data)
                store = parse_store(data)
            except:
                logger.error('Error {}: {}'.format(item_url, traceback.format_exc()))
                logger.info('Try again {} in {} seconds'.format(item_url, i + 1))
                time.sleep(i + 1)
            else:
                break
        else:
            logger.error('Failed {} after retries'.format(item_url))

        output.put({
            'item_url': item_url,
            'department': department,
            'store': store
        })

        counter += 1

        if counter >= 1000:
            counter = 0

            # reset session
            session = requests.Session()


def parse_department(data):
    products = data.get('payload', {}).get('products', {})

    if products:
        selected_product = data.get('payload', {}).get('selected', {}).get('product')

        if selected_product:
            product = products[selected_product]
        else:
            product = products.values()[0]

        department = product.get('productAttributes', {}).get('productCategory', {}).get('categoryPath')

        if department and department != 'UNNAV':
            return re.sub('^Home Page/', '', department)

    products = data.get('payload', {}).get('idmlMap', {})

    if products:
        product = products.values()[0]

        department = product.get('modules', {}).get('GeneralInfo', {}).get('category_path_name', {}).get('displayValue')

        if department and department != 'UNNAV':
            return re.sub('^Home Page/', '', department)

    return 'No department'


def parse_store(data):
    if 'F55CDC31AB754BB68FE0B39041159D63' in data.get('payload', {}).get('sellers', {}):
        return '1P'

    return '3P'


def output_writer(output, directory):
    for data in iter(output.get, 'STOP'):
        try:
            output_dir = os.path.join(directory, data['department'])

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            output_filename = os.path.join(output_dir, 'items_{}.csv'.format(data['store']))

            with open(output_filename, 'ab') as output_file:
                out_csv = csv.writer(output_file)
                out_csv.writerow([data['item_url']])
        except:
            logger.error('Writer error {}: {}'.format(data, traceback.format_exc()))
            data['department'] = 'No department'
            output.put(data)

if __name__ == '__main__':

    args = get_args()

    setup_logger(path=args.log)

    tasks = mp.Queue(args.threads)
    output = mp.Queue()

    workers = list()

    for _ in range(args.threads):
        process = mp.Process(target=parse_item, args=(tasks, output))
        process.start()
        workers.append(process)

    if args.output:
        directory = args.output
    else:
        directory = os.path.split(args.items)[0]

    directory = os.path.join(directory, 'departments')

    writer = mp.Process(target=output_writer, args=(output, directory))
    writer.start()

    def add_tasks(items_file):
        items_csv = csv.reader(items_file)

        counter = 0

        for item_url in items_csv:
            tasks.put(item_url[0])

            counter += 1

            if counter % 10000 == 0:
                logger.info('Processed {} items'.format(counter))

    try:
        if os.path.splitext(args.items)[1] == '.zip':
            with zipfile.ZipFile(args.items, 'r') as zip_file:
                for info in zip_file.infolist():
                    logger.info('Processing {}'.format(info.filename))

                    items_file = zip_file.open(info)

                    add_tasks(items_file)
        elif os.path.splitext(args.items)[1] == '.csv':
            logger.info('Processing {}'.format(args.items))

            with open(args.items, 'r') as items_file:
                add_tasks(items_file)
    except:
        logger.error('Main thread error: {}'.format(traceback.format_exc()))

    for _ in workers:
        tasks.put('STOP')

    for process in workers:
        process.join()

    output.put('STOP')
    writer.join()

    logger.info('Zipping...')

    shutil.make_archive(directory, 'zip', root_dir=directory)
    shutil.rmtree(directory)

    logger.info('Done')
