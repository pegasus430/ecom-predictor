import inspect
import os
import logging
import pysftp

from importlib import import_module
from pkgutil import iter_modules
from config import RESOURCES_DIR


def load_parsers(path):
    def walk_modules(_path):
        mods = []
        mod = import_module(_path)
        mods.append(mod)
        if hasattr(mod, '__path__'):
            for _, sub_path, is_pkg in iter_modules(mod.__path__):
                full_path = _path + '.' + sub_path
                if is_pkg:
                    mods += walk_modules(full_path)
                else:
                    sub_mod = import_module(full_path)
                    mods.append(sub_mod)
        return mods
    parsers = {}
    for module in walk_modules(path):
        for obj in vars(module).itervalues():
            class_check = inspect.isclass(obj) and issubclass(obj, Parser)
            if class_check and obj.__module__ == module.__name__ and getattr(obj, 'company', None):
                parsers[obj.company] = obj
    return parsers


class Parser(object):
    # how to read products
    IMPORT_TYPE_PRODUCTS_AND_IMAGES = 0
    IMPORT_TYPE_PRODUCTS = 1
    IMPORT_TYPE_IMAGES = 2

    company = None  # company name, mandatory property

    def __init__(self, config, logger=None):
        self.config = config
        self.need_to_clear_sftp_files = False
        self.logger = logger or logging.getLogger(__name__)
        self._import_type = int(config.get('import_type', -1))

    def parse(self, files=None):
        products = {}
        if not files:
            files = self._load_from_sftp()
        if not files:
            self.logger.info('These are no files for parsing')
        for filename in files:
            self.logger.info('Parsing file: {}'.format(filename))
            products[os.path.basename(filename)] = self._parse(filename)

        return products

    def _parse(self, data):
        raise NotImplementedError

    def _filter_sftp_file(self, filename):
        return True

    def _load_from_sftp(self):
        files = []
        sftp_config = self.config.get('sftp')
        if sftp_config:
            cn_opts = pysftp.CnOpts()
            cn_opts.hostkeys = None

            with pysftp.Connection(
                    sftp_config.get('server'),
                    username=sftp_config.get('user'),
                    password=sftp_config.get('password'),
                    cnopts=cn_opts
            ) as sftp:
                with sftp.cd(sftp_config.get('dir')):
                    for filename in sftp.listdir():
                        if not self._filter_sftp_file(filename):
                            continue
                        if sftp.isfile(filename):
                            self.logger.info('Loading file from SFTP: {}'.format(filename))
                            local_filename = os.path.join(RESOURCES_DIR, filename)
                            sftp.get(filename, local_filename)
                            os.chmod(local_filename, 0o777)  # to not have issues with permissions in further
                            files.append(local_filename)
                            if not sftp.lexists('processed'):
                                sftp.mkdir('processed')
                            sftp.rename(filename, 'processed/{}'.format(filename))
        if files:
            self.need_to_clear_sftp_files = True
        return files

    def _remove_sftp_files(self, files):
        if files and self.need_to_clear_sftp_files:
            for f in files:
                os.remove(f)
