import boto
import json
import re
import traceback
from datetime import datetime

import xlrd

from . import Parser


class AbbottParser(Parser):
    company = 'abbott'

    filename_pattern = 'Salsify_abbott-production-account_content_analytics_abbott_{date}T\d{{6}}.xlsx'

    def __init__(self, *args, **kwargs):
        self.run_dt = datetime.now()

        self.converters_mapping = {
            'amazon': AmazonProductConverter,
            'amazon pantry': AmazonPantryProductConverter,
            'walmart': WalmartProductConverter,
            'target': TargetProductConverter,
            'jet': JetProductConverter
        }

        self.compiled_filename_pattern = re.compile(self.filename_pattern.format(date=self.run_dt.strftime('%Y-%m-%d')))
        super(AbbottParser, self).__init__(*args, **kwargs)
        self.logger.info('Abbott parser start datetime: {0}'.format(self.run_dt.strftime('%Y-%m-%d %H:%M:%S')))

    def parse(self, files=None):
        files = self._load_from_sftp()
        if not files:
            self.logger.info('These are no files for parsing')

        # for abbott parser we need to send multiple customers and we have only one file per run
        # to make customer name configurable we will send it in filename
        if len(files) != 1:
            self.logger.error(
                'There are multiple files ({0}) for parsing (only one expected). '
                'Will be used first one.'.format(len(files))
            )
        xlsx_path = files[0]
        self.logger.info('Parsing file: {}'.format(xlsx_path))
        customers_and_products = self._parse(xlsx_path)
        return customers_and_products

    def _parse(self, filename):
        products_map = {}
        workbook = xlrd.open_workbook(filename)
        sheet_names = workbook.sheet_names()
        self.logger.debug('Got {0} sheets for parsing in xlsx file'.format(len(sheet_names)))
        for sheet_name in sheet_names:
            converter_class = self.converters_mapping.get(sheet_name.strip().lower())
            if not converter_class:
                self.logger.warning('No converter for sheet "{}"'.format(sheet_name))
                continue
            self.logger.debug('Processing data for "{}" retailer'.format(sheet_name))
            sheet = workbook.sheet_by_name(sheet_name)
            converter = converter_class(sheet, self.logger)
            retailer_products = converter.convert()
            for product in retailer_products:
                self._prepare_product_for_mc(product)
            self.logger.debug('{} products parsed for retailer {}'.format(len(retailer_products), sheet_name))
            products_map[sheet_name] = retailer_products

        return products_map

    def _prepare_product_for_mc(self, product):
        try:
            # id
            upc = product['upc']
            del product['upc']
            product['id_value'] = upc
            product['id_type'] = 'upc'
            # bullets
            if product.get('bullets'):
                product['bullets'] = json.dumps(product['bullets'])
            # images
            if product.get('images'):
                product['images'] = dict((url, i) for i, url in enumerate(product['images'], 1))
        except Exception as e:
            self.logger.error('Product parsing error: "{0}"'.format(e.message))
            self.logger.debug('Product data with error:\n{0}'.format(json.dumps(product, indent=4)))

    def _filter_sftp_file(self, filename):
        if self.compiled_filename_pattern.match(filename):
            return True
        return False

    def _load_from_sftp(self, *arga, **kwargs):
        files = super(AbbottParser, self)._load_from_sftp()
        if files:
            self._notify_sftp_file_retrieved()
        return files

    def _notify_sftp_file_retrieved(self):
        try:
            ses = boto.connect_ses()
            ses.send_email(
                source='retailer@contentanalyticsinc.com',
                subject='Abbott CAI Data Feed',
                body='File has been delivered to SFTP server. ',
                to_addresses=['an.ecommerce@abbott.com', 'support@contentanalyticsinc.com']
            )
        except:
            self.logger.error('Can not send email, check AWS settings')
            self.logger.error('Error: {}'.format(traceback.format_exc()))


class BaseProductConverter(object):
    retailer = None

    def __init__(self, sheet, logger):
        self._sheet = sheet
        self.logger = logger
        super(BaseProductConverter, self).__init__()

    def get_mapping(self):
        # field names: (Retailer xlsx name: MC name)
        return {
            'SKU/UPC': 'upc',
            'ATF Image Order Main': 'main_image',
            'ATF Image Order': 'images'
        }

    def get_product_boilerplate(self):
        # product template with empty fields. Field type (string/list) used during conversion
        return {
            'upc': '',
            'main_image': '',
            'images': [],
        }

    @staticmethod
    def _post_process_images(product):
        # put main image before all other images
        if product.get('main_image'):
            product['images'] = [product.get('main_image')] + product.get('images', [])
            del product['main_image']

    def convert(self):
        rows = self._sheet.get_rows()
        headers = [h.value.strip() for h in rows.next()]
        products = []
        for row in rows:
            product = self.get_product_boilerplate()
            for index, header in enumerate(headers):
                if header not in self.get_mapping():
                    self.logger.warning('No mapping for column "{}", retailer is "{}".'.format(header, self.retailer))
                    continue
                mc_field_name = self.get_mapping()[header]

                if isinstance(product.get(mc_field_name), basestring):
                    if row[index].value:
                        product[mc_field_name] += row[index].value
                elif isinstance(product.get(mc_field_name), list):
                    if row[index].value:
                        product[mc_field_name].append(row[index].value)
            # put main image before all other images
            self._post_process_images(product)
            products.append(product)
        return products


class BulletsMixin(object):
    def get_product_boilerplate(self):
        boilerplate = super(BulletsMixin, self).get_product_boilerplate()
        boilerplate.update({
            'bullets': [],
        })
        return boilerplate

    def get_mapping(self):
        mapping = super(BulletsMixin, self).get_mapping()
        mapping.update({
            'Bullet 1': 'bullets',
            'Bullet 2': 'bullets',
            'Bullet 3': 'bullets',
            'Bullet 4': 'bullets',
            'Bullet 5': 'bullets',
        })
        return mapping


class AmazonMixin(object):
    def get_product_boilerplate(self):
        boilerplate = super(AmazonMixin, self).get_product_boilerplate()
        boilerplate.update({
            'asin': '',
            'product_name': '',
            'long_description': '',
        })
        return boilerplate

    def get_mapping(self):
        mapping = super(AmazonMixin, self).get_mapping()
        mapping.update({
            'Amazon RPC': 'asin',
            'Amazon Classic Product Name': 'product_name',
            'Product Description': 'long_description',
        })
        return mapping


class AmazonProductConverter(BulletsMixin, AmazonMixin, BaseProductConverter):
    retailer = 'Amazon'


class AmazonPantryProductConverter(BulletsMixin, AmazonMixin, BaseProductConverter):
    retailer = 'AmazonPantry'

    def get_mapping(self):
        mapping = super(AmazonPantryProductConverter, self).get_mapping()
        mapping.pop('Amazon RPC', None)
        mapping.update({
            'Amazon Pantry RPC': 'asin'
        })
        return mapping


class WalmartProductConverter(BaseProductConverter):
    retailer = 'Walmart'

    def get_product_boilerplate(self):
        boilerplate = super(WalmartProductConverter, self).get_product_boilerplate()
        boilerplate.update({
            'tool_id': '',
            'product_name': '',
            'description': '',
            'long_description': ''

        })
        return boilerplate

    def get_mapping(self):
        mapping = super(WalmartProductConverter, self).get_mapping()
        mapping.update({
            'Walmart RPC': 'tool_id',
            'Amazon Classic Product Name': 'product_name',
            'Product Description': 'description',
            'Bullet 1': 'long_description',
            'Bullet 2': 'long_description',
            'Bullet 3': 'long_description',
            'Bullet 4': 'long_description',
            'Bullet 5': 'long_description',
        })
        return mapping


class TargetProductConverter(BulletsMixin, BaseProductConverter):
    retailer = 'Target'

    def get_product_boilerplate(self):
        boilerplate = super(TargetProductConverter, self).get_product_boilerplate()
        boilerplate.pop('main_image', None)
        boilerplate.update({
            'tcin': '',
            'product_name': '',
            'description': '',

        })
        return boilerplate

    def get_mapping(self):
        mapping = super(TargetProductConverter, self).get_mapping()
        mapping.pop('ATF Image Order Main', None)
        mapping.pop('ATF Image Order', None)
        mapping.update({
            'TCIN': 'tcin',
            'Target Product Name': 'product_name',
            'Product Description': 'description',
            'Image': 'images'
        })
        return mapping


class JetProductConverter(BulletsMixin, BaseProductConverter):
    retailer = 'Jet'

    def get_product_boilerplate(self):
        boilerplate = super(JetProductConverter, self).get_product_boilerplate()
        boilerplate.update({
            'product_name': '',
            'description': ''

        })
        return boilerplate

    def get_mapping(self):
        mapping = super(JetProductConverter, self).get_mapping()
        mapping.update({
            'Amazon Classic Product Name': 'product_name',
            'Product Description': 'description',
        })
        return mapping
