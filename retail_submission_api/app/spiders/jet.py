import gzip
import json
import shutil
import time
from StringIO import StringIO

import re
import requests

from . import SubmissionSpider, SubmissionSpiderError


class JetSubmissionSpider(SubmissionSpider):
    retailer = 'jet.com'
    driver_engine = None  # don't use web driver

    token_endpoint = 'https://merchant-api.jet.com/api/token'
    sku_upload_endpoint = 'https://merchant-api.jet.com/api/merchant-skus/{sku}'

    sku_bulk_upload_token_endpoint = 'https://merchant-api.jet.com/api/files/uploadToken'
    sku_bulk_upload_process_endpoint = 'https://merchant-api.jet.com/api/files/uploaded'
    sku_bulk_upload_check_endpoint = 'https://merchant-api.jet.com/api/files/{file_id}'

    submission_filename = 'MerchantSKUs.json'

    max_retries = 10

    def _get_sku(self, product):
        sku = product.get('vendor_item_sku_number')
        upc = product.get('upc')
        asin = product.get('asin')
        gtin = product.get('gtin')

        if sku:
            return sku
        if upc:
            return upc[-12:].zfill(12)
        elif asin:
            return asin
        elif gtin:
            return gtin

    def _get_jet_product(self, product):
        jet_product = {
            'product_description': product.get('description') or '',
            'manufacturer': product.get('primary_seller') or '',
            'bullets': self._get_bullets(product),
            'brand': product.get('brand') or '',
            'product_title': product.get('product_name') or '',
            'safety_warning': product.get('safety_warnings') or '',
            'multipack_quantity': 1
        }

        asin = product.get('asin')
        upc = product.get('upc')
        gtin = product.get('gtin')

        if asin:
            jet_product['asin'] = asin
        elif upc:
            jet_product['standard_product_codes'] = [{
                'standard_product_code': upc[-12:].zfill(12),
                'standard_product_code_type': 'UPC'
            }]
        elif gtin:
            jet_product['standard_product_codes'] = [{
                'standard_product_code': gtin,
                'standard_product_code_type': 'GTIN'
            }]
        else:
            raise SubmissionSpiderError(
                "Product ({}) hasn't ASIN, UPC or GTIN. Upload impossible".format(product.get("id")))

        images = product.get('image_urls') or []

        if not images:
            raise SubmissionSpiderError("Product ({}) hasn't images. Upload impossible".format(product.get("id")))

        jet_product['main_image_url'] = images[0]

        if len(images) > 1:
            jet_product['alternate_images'] = [{'image_slot_id': i, 'image_url': image}
                                               for i, image in enumerate(images[1:9], 1)]

        return jet_product

    def _get_bullets(self, product):
        bullets = product.get('bullets') or []

        if not bullets:
            description = product.get('long_description') or product.get('description')

            if description:
                bullets = self._extract_bullets(description)
        elif len(bullets) == 1 and '<li>' in bullets[0]:
            bullets = self._extract_bullets(bullets[0])

        return [bullet[:500] for bullet in bullets][:5]

    def _extract_bullets(self, text):
        match = re.search(r'<ul>(.*?)</ul>', text)

        return re.findall(r'(?:<li>(.*?)</li>)+?', match.group(1) if match else text)

    def _get_auth_headers(self, options):
        if self.sandbox or not options.get('do_submit'):
            if 'test' not in options:
                raise SubmissionSpiderError('Missing test API keys')

            api_keys = options['test']
        else:
            if 'live' not in options:
                raise SubmissionSpiderError('Missing live API keys')

            api_keys = options['live']

        for i in range(self.max_retries):
            response = requests.post(self.token_endpoint, data=json.dumps(api_keys))

            if response.status_code != 200:
                self.logger.debug('Response {}: {}'.format(response.status_code, response.content))
                self.logger.info('Retry token request {}'.format(i+1))
                time.sleep(1)
                continue

            token = response.json()["id_token"]

            headers = {"Content-Type": "application/json",
                       "Authorization": "bearer {}".format(token)}

            return headers
        else:
            raise SubmissionSpiderError('Token was not received')

    def _bulk_upload(self, jet_filename, headers):
        self.logger.info('Start bulk upload')

        gzip_buf = StringIO()

        with open(jet_filename) as jet_file, gzip.GzipFile(fileobj=gzip_buf, mode='w') as gzip_file:
            shutil.copyfileobj(jet_file, gzip_file)

        self.logger.info('Getting upload token')
        response = requests.get(self.sku_bulk_upload_token_endpoint, headers=headers)

        if response.status_code not in [200, 201, 202]:
            self.logger.debug('Response: {}'.format(response.content))
            raise SubmissionSpiderError('Token for bulk-upload was not received: {}'.format(response.status_code))

        token_data = response.json()
        upload_url = token_data['url']

        self.logger.info('Uploading JSON to url: {}'.format(upload_url))

        upload_headers = {'x-ms-blob-type': 'blockblob'}
        response = requests.put(upload_url, headers=upload_headers, data=gzip_buf.getvalue())

        if response.status_code not in [200, 201, 202]:
            self.logger.debug('Response: {}'.format(response.content))
            raise SubmissionSpiderError("File was not uploaded. Server return {} error".format(response.status_code))

        self.logger.info('Run JSON processing')
        request_data = {
            'url': token_data['url'],
            'file_type': 'MerchantSKUs',
            'file_name': self.submission_filename
        }
        response = requests.post(self.sku_bulk_upload_process_endpoint, data=json.dumps(request_data), headers=headers)
        if response.status_code not in [200, 201, 202]:
            self.logger.debug('Response: {}'.format(response.content))
            raise SubmissionSpiderError("File was not processed. Server return {} error".format(response.status_code))

        self.data['jet_file_id'] = token_data['jet_file_id']
        self.async_check_required = True

    def _merchant_upload(self, sku, product, headers):
        response = requests.put(self.sku_upload_endpoint.format(sku=sku), headers=headers, data=json.dumps(product))

        if response.status_code not in [200, 201, 202]:
            self.logger.debug('Response: {}'.format(response.content))
            raise SubmissionSpiderError('SKU {} upload error {}: {}'.format(
                sku, response.status_code, response.json().get('errors') if response.content else ''))

    def _merchant_retrieval(self, sku, headers):
        response = requests.get(self.sku_upload_endpoint.format(sku=sku), headers=headers)

        if response.status_code == 404:
            return

        if response.status_code not in [200, 201, 202]:
            self.logger.debug('Response: {}'.format(response.content))
            raise SubmissionSpiderError('SKU {} retrieval error {}: {}'.format(
                sku, response.status_code, response.json().get('error') if response.content else ''))

        return response.json()

    def task_content(self, options, products, **kwargs):
        self.logger.info("Preparing Jet JSON")

        jet_data = {}

        for product in products:
            sku = self._get_sku(product)

            if not sku:
                raise SubmissionSpiderError("Product ({}) hasn't SKU".format(product.get("id")))
            else:
                self.data.setdefault('products', []).append({
                    'product_id': product.get("id"),
                    'sku': sku
                })

            jet_data[sku] = self._get_jet_product(product)

        jet_filename = self.get_file_path_for_result(self.submission_filename)
        with open(jet_filename, 'wb') as jet_file:
            json.dump(jet_data, jet_file, indent=2)

        headers = self._get_auth_headers(options)

        if True:  # use bulk upload always
            self._bulk_upload(jet_filename, headers)
        else:
            for sku, product in jet_data.iteritems():
                self.logger.info("Uploading SKU: {}".format(sku))

                self._merchant_upload(sku, product, headers)

        self.logger.info('Products were uploaded')

    def task_check(self, options, **kwargs):
        self.logger.info('Checking submission status')

        jet_file_id = options['jet_file_id']
        headers = self._get_auth_headers(options)

        response = requests.get(self.sku_bulk_upload_check_endpoint.format(file_id=jet_file_id),
                                headers=headers)

        if response.status_code not in [200, 201, 202]:
            self.logger.debug('Response: {}'.format(response.content))
            raise SubmissionSpiderError("Status check failed. Server return {} error".format(response.status_code))

        status_data = response.json()
        status = status_data.get('status')
        self.logger.info('Current status: {}'.format(status))

        if status in ('Processed successfully', 'Processed with errors'):
            time.sleep(60)  # additional pause to avoid 404

            for product in options['products']:
                jet_product = self._merchant_retrieval(product['sku'], headers)

                if jet_product:
                    product.update({
                        'sku_status': jet_product.get('status'),
                        'sku_substatus': ', '.join(jet_product.get('sub_status', []))
                    })
                else:
                    product.update({
                        'sku_status': 'unavailable',
                        'sku_substatus': ''
                    })

                self.data.setdefault('products', []).append(product)

            if status == 'Processed successfully':
                self.async_check_required = False
                self.logger.info('Bulk file was processed successfully')
            else:
                self.logger.debug('Response: {}'.format(response.content))
                raise SubmissionSpiderError('Process errors: {}'.format(status_data.get('error_url')))
        else:
            self.async_check_required = True
