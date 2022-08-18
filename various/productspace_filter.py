import argparse
import logging
import os
import re
import xlrd
from xlutils.copy import copy

logger = logging.getLogger(__name__)


def get_args():
    """
    Parse command line arguments

    :return: command line arguments
    """

    parser = argparse.ArgumentParser(description='Timemachine. Script to take snapshots of files')

    parser.add_argument('product_space',
                        help='Product space XLS file path')

    parser.add_argument('gtin_filter',
                        help='Filter XLS file path')

    parser.add_argument('-s', '--sheet',
                        help='Sheet name in filter file with GTIN column')

    parser.add_argument('-o', '--output',
                        help='Output file for filtered product space file')

    parser.add_argument('-l', '--log',
                        help='Log file path')

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


def parse_gtin_filter(gtin_filter_file, sheet=None):
    print "Parsing filter file: {}".format(gtin_filter_file)

    wb = xlrd.open_workbook(gtin_filter_file)
    ws = wb.sheet_by_name(sheet) if sheet else wb.sheet_by_index(0)

    rows = ws.get_rows()

    header = [h.value.strip().lower() for h in rows.next()]

    try:
        gtin_column_index = header.index('gtin')
    except ValueError:
        print 'There is not GTIN column on {} sheet'.format(ws.name)
        exit()

    gtin_filter = set()

    for row in rows:
        gtin = row[gtin_column_index].value.strip()

        if re.match(r'\d+', gtin):
            gtin_filter.add(gtin)

    return gtin_filter


def filter_product_space(product_space_file, gtin_filter, output=None):
    print "Parsing product space file: {}".format(product_space_file)

    wb = xlrd.open_workbook(product_space_file)
    ws = wb.sheet_by_name('Products')

    wb_filter = copy(wb)
    ws_filter = wb_filter.get_sheet(ws.name)

    rows = ws.get_rows()
    # header row 1
    header = [h.value.strip().lower() for h in rows.next()]
    try:
        gtin_column_index = header.index('gtin')
    except ValueError:
        print 'There is not GTIN column on {} sheet'.format(ws.name)
        exit()

    # skip description row 2
    rows.next()
    # skip requirements 3
    rows.next()

    ws_filter_row_index = 3
    ws_filter_latest_row_index = ws.nrows - 1

    for row in rows:
        if row[gtin_column_index].value in gtin_filter:
            for cell_index, cell in enumerate(row):
                ws_filter.write(ws_filter_row_index, cell_index, cell.value)
            ws_filter_row_index += 1
        else:
            # erase the latest row
            for cell_index in range(ws.ncols):
                ws_filter.write(ws_filter_latest_row_index, cell_index, None)
            ws_filter_latest_row_index -= 1

    if not output:
        output = os.path.splitext(product_space_file)
        output = '{}_filter{}'.format(output[0], output[1])

    wb_filter.save(output)

if __name__ == '__main__':

    args = get_args()

    setup_logger(path=args.log)

    gtin_filter = parse_gtin_filter(args.gtin_filter, args.sheet)

    filter_product_space(args.product_space, gtin_filter, args.output)
