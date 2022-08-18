import argparse
import logging
import requests
import os
import json
import shutil
import csv
import boto
import xlrd
import multiprocessing as mp
import traceback

from threading import Thread
from datetime import datetime
from boto.s3.key import Key
from dateutil.parser import parse

logger = logging.getLogger(__name__)


def get_args():
    """
    Parse command line arguments
    :return: command line arguments
    """
    parser = argparse.ArgumentParser(description='Download PepsiCo images')
    parser.add_argument('images', help='CSV or XLS file with images')
    parser.add_argument('-o', '--output', default='images', help='Saving dir for images')
    parser.add_argument('-b', '--bucket', help='S3 bucket for images')
    parser.add_argument('-l', '--log', default='pepsico_images.log', help='Log file path')
    return parser.parse_args()


def setup_logger(log, log_level=logging.DEBUG, path=None):
    """
    Setup logger formats and handlers

    :param log: logger
    :param log_level: logging level
    :param path: log file path
    :return:
    """

    log.setLevel(log_level)

    log_format = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
    log_format.datefmt = '%Y-%m-%d %H:%M:%S'

    log_stdout = logging.StreamHandler()
    log_stdout.setFormatter(log_format)
    log_stdout.setLevel(log_level)
    log.addHandler(log_stdout)

    if path:
        log_file = logging.FileHandler(path)
        log_file.setFormatter(log_format)
        log_file.setLevel(log_level)
        log.addHandler(log_file)


class PepsiCoImages(object):

    def __init__(self, input_file, log=None, workers=10, images_filter=None):
        self.images_filter = images_filter
        if log:
            self.log = log
        else:
            self.log = logging.getLogger(__name__)
            setup_logger(self.log)

        if input_file.endswith('.csv'):
            images = self._read_images_from_csv(input_file)
        elif input_file.endswith('.xls'):
            images = self._read_images_from_xls(input_file)
        else:
            raise AttributeError('Input file has not CSV or XLS format')

        self.images = self._sort_images(images)
        self._start_workers(workers)

    def _start_workers(self, workers):
        self.workers = []
        self.tasks = mp.Queue(workers)
        self.output = mp.Queue()

        for worker_id in range(workers):
            thread = Thread(target=self._download_worker, args=(self.tasks, self.output))
            thread.daemon = True
            thread.start()
            self.workers.append(thread)

    def _stop_workers(self):
        for _ in self.workers:
            self.tasks.put('STOP')

        for thread in self.workers:
            if thread.is_alive():
                thread.join(60)

    def _read_images_from_csv(self, csv_file):
        with open(csv_file, 'rb') as images_file:
            header = [h.strip() for h in images_file.next().split(',')]
            images_csv = csv.DictReader(images_file, fieldnames=header)
            images = list(images_csv)
            if not self.images_filter or not callable(self.images_filter):
                return images
            filtered = []
            for image in images:
                if not self.images_filter(image):
                    self.log.debug('Filtered out image:\n {}'.format(json.dumps(image, indent=2)))
                    continue
                filtered.append(image)
            return filtered

    def _read_images_from_xls(self, xls_file):
        def get_cell_value(cell):
            if cell.ctype == xlrd.XL_CELL_DATE:
                return xlrd.xldate.xldate_as_datetime(cell.value, workbook.datemode).strftime('%d-%b-%y')
            else:
                value = cell.value
                if isinstance(value, basestring) and not value.isdigit():
                    try:
                        dt = parse(value)
                        value = dt.strftime('%d-%b-%y')
                    except:
                        pass
                return value

        workbook = xlrd.open_workbook(xls_file)
        sheet = workbook.sheet_by_name('Images')
        rows = sheet.get_rows()
        header = [h.value.strip() for h in rows.next()]
        images = []

        for row in rows:
            image = dict(zip(header, map(get_cell_value, row)))
            if self.images_filter and callable(self.images_filter):
                if not self.images_filter(image):
                    self.log.debug('Filtered out image:\n {}'.format(json.dumps(image, indent=2)))
                    continue
            images.append(image)
        return images

    def _sort_images(self, images):

        def _to_str(_view):
            # in some cases "view" is float - need to remove ".0" from result string
            if isinstance(_view, float):
                return '{0:.0f}'.format(_view)
            if _view is None:
                return ''
            return str(_view)

        def sort_images(x, y):
            """
            Sort images in order:
            1) priority for non digit View
            2) sort as usual if Views are not equal
            3) priority for Image Source Code = Schawk if Views are equal
            4) priority for later Effective Start Date if Views and Image Source Code are equal
            """

            x_view = _to_str(x.get('View'))
            y_view = _to_str(y.get('View'))

            if x_view != y_view:
                if x_view.isdigit() and not y_view.isdigit():
                    return 1
                elif not x_view.isdigit() and y_view.isdigit():
                    return -1
                else:
                    return cmp(x_view, y_view)
            else:
                x_code = x.get('Image Source Code', '')
                y_code = y.get('Image Source Code', '')

                if x_code == 'Schawk' and y_code != 'Schawk':
                    return -1
                elif x_code != 'Schawk' and y_code == 'Schawk':
                    return 1

                x_date = datetime.strptime(x.get('Effective Start Date', '01-Jan-90'), '%d-%b-%y')
                y_date = datetime.strptime(y.get('Effective Start Date', '01-Jan-90'), '%d-%b-%y')

                return cmp(y_date, x_date)

        gtin_images = {}

        for image in images:
            dt_start = image.get('Effective Start Date')
            dt_end = image.get('Effective End Date')

            if (not dt_start or datetime.now() >= datetime.strptime(dt_start, '%d-%b-%y')) \
                    and (not dt_end or datetime.now() < datetime.strptime(dt_end, '%d-%b-%y')):
                gtin_images.setdefault(image['GTIN Number'], []).append(image)
            else:
                self.log.warn(
                    'Skip due dates view {} for GTIN {}: {}'.format(
                        image.get('View'), image.get('GTIN Number'), image.get('Uniform Resource Identifier')
                    )
                )
        gtin_images_sorted = {}
        for gtin, images in gtin_images.iteritems():
            images_sorted = []
            prev_image = None

            for image in sorted(images, cmp=sort_images):
                if prev_image is not None:
                    if prev_image.get('View', '') == image.get('View', ''):
                        # skip duplicate View or download both
                        if prev_image.get('Image Source Code', '') == 'Schawk'\
                                and image.get('Image Source Code', '') != 'Schawk':
                            self.log.warn('Skip duplciate view {} for GTIN {}: {}'.
                                          format(image.get('View'),
                                                 gtin,
                                                 image.get('Uniform Resource Identifier')))
                            continue
                        else:
                            if prev_image.get('Effective Start Date', '') != image.get('Effective Start Date', ''):
                                self.log.warn('Skip duplciate view {} for GTIN {}: {}'.
                                              format(image.get('View'),
                                                     gtin,
                                                     image.get('Uniform Resource Identifier')))
                                continue
                            else:
                                images_sorted.append(prev_image)
                                prev_image = image
                    else:
                        images_sorted.append(prev_image)
                        prev_image = image
                else:
                    prev_image = image

            if prev_image:
                images_sorted.append(prev_image)

            # remove low resolution View
            images_filtered = []

            for image in images_sorted:
                view = _to_str(image.get('View'))

                if view and view[0] == 'A' and any(x.get('View') == 'C' + view[1:] for x in images_sorted):
                    self.log.warn('Skip low resolution view {} for GTIN {}: {}'.
                                  format(image.get('View'),
                                         gtin,
                                         image.get('Uniform Resource Identifier')))
                    continue

                images_filtered.append(image)

            image_urls_seen = set()

            for index, image in enumerate(images_filtered):
                image_url = image.get('Uniform Resource Identifier', '')
                image_view = _to_str(image.get('View'))
                image_type = image_url.split('.')[-1]

                if 'jpg' not in image_type and 'jpeg' not in image_type and 'tif' not in image_type:
                    image_type = 'jpg'

                image_name = '{}_{}_{}.{}'.format(gtin, index, image_view, image_type)

                if image_url in image_urls_seen:
                    self.log.error('Duplicate image url: {}'.format(image_url))

                image_urls_seen.add(image_url)

                gtin_images_sorted.setdefault(gtin, []).append({'name': image_name, 'url': image_url})

        return gtin_images_sorted

    def _download_worker(self, tasks, output):
        for task in iter(tasks.get, 'STOP'):
            try:
                image_name, image_url, image_dir, bucket = task

                filename = os.path.join(image_dir, image_name)
                result = None

                try:
                    if not os.path.exists(filename):
                        self.log.info('Getting - {}'.format(image_name))

                        response = requests.get(image_url, stream=True, verify=False)
                        with open(filename, 'wb') as image_file:
                            shutil.copyfileobj(response.raw, image_file)
                        del response
                except Exception as e:
                    self.log.error('error getting - {} - {}'.format(image_name, e))
                else:
                    result = filename

                if bucket:
                    try:
                        s3_conn = boto.connect_s3()
                        s3_bucket = s3_conn.get_bucket(bucket, validate=False)

                        s3_key = Key(s3_bucket)
                        s3_key.key = filename

                        if not s3_key.exists():
                            self.log.info('Uploading - {}'.format(image_name))

                            s3_key.set_contents_from_filename(filename)

                        s3_url = s3_key.generate_url(expires_in=0, query_auth=False)
                    except Exception as e:
                        self.log.error('Can not upload image {} to S3: {}'.format(image_name, e))
                    else:
                        os.remove(filename)
                        result = s3_url.split('?')[0]

                output.put((image_name, result))
            except Exception:
                self.log.error('Exception on image download:')
                self.log.error(traceback.format_exc())

    def download(self, gtin=None, image_dir='images', bucket=None):
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)

        if gtin:
            images = self.images.get(gtin, [])
            for image in images:
                self.tasks.put((image['name'], image['url'], image_dir, bucket))

            for _ in range(len(images)):
                name, result = self.output.get()

                for image in images:
                    if image['name'] == name:
                        image['url'] = result

            return images
        else:
            for gtin, images in self.images.iteritems():
                for image in images:
                    self.tasks.put((image['name'], image['url'], image_dir, bucket))

if __name__ == '__main__':

    args = get_args()

    setup_logger(log=logger, path=args.log)

    if not os.path.isfile(args.images):
        logger.error('Images file does not exist: {}'.format(args.images))
        exit()

    pepsico_images = PepsiCoImages(args.images, log=logger)
    pepsico_images.download(image_dir=args.output, bucket=args.bucket)
    pepsico_images._stop_workers()
