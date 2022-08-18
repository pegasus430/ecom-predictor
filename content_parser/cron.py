import argparse
import logging
import os
import traceback
import json

from parsers import load_parsers
from cron_config import CronConfig
from mc.api import ImportAPI

logger = logging.getLogger(__name__)


def get_args():
    """
    Parse command line arguments

    :return: command line arguments
    """

    parser = argparse.ArgumentParser(description='Parse and import products')

    parser.add_argument('company',
                        help='Company name')

    parser.add_argument('-c', '--config',
                        default='cron_config.json',
                        help='Configuration file path')

    parser.add_argument('-l', '--log',
                        default='cron.log',
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


if __name__ == '__main__':

    args = get_args()

    setup_logger(path=args.log)

    logger.info('Processing company: {}'.format(args.company))

    if not os.path.exists(args.config):
        logger.error('Config file does not exist: {}'.format(args.config))
        exit()

    config = CronConfig(args.config).get(args.company)

    if not config:
        logger.error('Config for company does not exist: {}'.format(args.company))
        exit()

    parser_class = load_parsers('parsers').get(args.company)

    if not parser_class:
        logger.error('Parser for company does not exist: {}'.format(args.company))
        exit()

    parser = parser_class(config=config, logger=logger)
    data = None
    try:
        logger.info('Parse')
        data = parser.parse()
    except:
        logger.error('Parse failed: {}'.format(traceback.format_exc()))
        exit()

    if data:
        logger.debug('Data for import:\n{}'.format(json.dumps(data, indent=2)))
        importer = ImportAPI(config=config, logger=logger)
        try:
            logger.info('Import')
            importer.import_data(data)
        except:
            logger.error('Import failed: {}'.format(traceback.format_exc()))
            exit()

    logger.info('Done')
