import traceback
import os
import logging
import json
import config

from celery import Celery, current_task
from celery.states import PENDING
from mc.api import ImportAPI
from parsers import load_parsers

from celery.utils.log import get_task_logger
task_logger = get_task_logger(__name__)

os.environ.setdefault('CELERY_CONFIG_MODULE', 'config')
celery = Celery()

available_parsers = load_parsers(config.PARSERS_PACKAGE)


@celery.task(bind=True)
def import_products(self, parser_name, import_config, products_file):
    task_result = {}

    def _add_log_file(_logger, _path):
        _logger.setLevel(logging.DEBUG)

        log_format = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
        log_format.datefmt = '%Y-%m-%d %H:%M:%S'

        log_file = logging.FileHandler(_path)
        log_file.setFormatter(log_format)
        log_file.setLevel(logging.DEBUG)
        logger.addHandler(log_file)

    def _free_log_handlers(_logger):
        if not _logger:
            return
        for handler in _logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                _logger.removeHandler(handler)

    logger = None
    try:
        request_id = self.request.id
        log_path = os.path.join(config.RESOURCES_DIR, '{}.log'.format(request_id))
        task_result['log'] = log_path
        logger = logging.getLogger(request_id)
        _add_log_file(logger, log_path)
        this_task = current_task

        logger.debug('Config for parser "{}":\n{}'.format(parser_name, json.dumps(import_config, indent=2)))
        parser_class = available_parsers.get(parser_name)
        if parser_class:
            parser = parser_class(config=import_config, logger=logger)
            data = None

            try:
                logger.info('Parse')
                this_task.update_state(state=PENDING, meta={'progress': 'File parsing'})
                data = parser.parse(files=[products_file])
            except:
                logger.error('Parse failed: {}'.format(traceback.format_exc()))
            finally:
                try:
                    if products_file is not None:  # removing saved file (we don't need it anymore)
                        os.remove(products_file)
                except OSError as os_err:
                    logger.error('Cannot remove source file ({0}).'.format(os_err.message))
            if data:
                logger.debug('Data for import:\n{}'.format(json.dumps(data, indent=2)))
                importer = ImportAPI(config=import_config, logger=logger)
                try:
                    logger.info('Import')
                    this_task.update_state(state=PENDING, meta={'progress': 'Importing'})
                    importer.import_data(data)
                except:
                    logger.error('Import failed: {}'.format(traceback.format_exc()))
                else:
                    logger.info('Done')
        else:
            logger.error('Parser "{}" does not exist. Check parser name or reload Celery'.format(parser_name))
    except Exception as e:
        task_result['error'] = e.message
        task_result['stacktrace'] = traceback.format_exc()
    finally:
        _free_log_handlers(logger)
        return task_result
