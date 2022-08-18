import csv
import json
import os
import re
import time
import traceback
from copy import copy
from urlparse import urljoin

import requests

from . import SitemapSpider, SitemapSpiderError


class TargetSitemapSpider(SitemapSpider):
    retailer = 'target.com'

    domain = 'http://www.target.com'

    SHELF_SITEMAP_URL = 'https://www.target.com/c/sitemap_001.xml.gz'

    API_URL_TEMPLATE = 'http://redsky.target.com/v1/plp/search?count=24&' \
                       'offset={offset}&' \
                       'category={category_id}&' \
                       'faceted_value={filter_id}'

    def task_sitemap_to_shelf_to_item_urls(self, options):
        options['urls'] = list(self._parse_sitemap(self.SHELF_SITEMAP_URL))

        self.task_shelf_to_item_urls(options)

    def task_sitemap_to_item_urls(self, options):
        self.task_sitemap_to_shelf_to_item_urls(options)

        # join all files without duplicates
        item_ids_seen = set()
        results = copy(self._results)

        with open(self.get_file_path_for_result('item_urls.csv'), 'w') as item_urls_file:
            for result in results:
                if os.path.exists(result):
                    with open(result) as items_urls:
                        for item_url in items_urls:
                            item_id = item_url.strip().split('/')[-1]

                            if item_id not in item_ids_seen:
                                item_urls_file.write(item_url)
                                item_ids_seen.add(item_id)
                    os.remove(result)
                else:
                    self.logger.warn('Result file {} does not exist'.format(result))

    def task_sitemap_to_shelf_urls(self, options):
        with open(self.get_file_path_for_result('shelf_urls.csv'), 'w') as shelf_urls_file:
            shelf_urls_writer = csv.writer(shelf_urls_file)

            for shelf_url in self._parse_sitemap(self.SHELF_SITEMAP_URL):
                shelf_urls_writer.writerow([shelf_url])

    def task_shelf_to_item_urls(self, options):
        missing_options = {'urls'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        shelf_urls = options.get('urls', [])
        exclude = options.get('exclude', [])
        
        failed_urls = []
        for shelf_url in shelf_urls:
            try:
                category = re.search(r'/c/([^/]+)(?:/[^/]+)*/-/N-([a-z0-9]+)(?:Z([a-z0-9Z]+))?', shelf_url)

                if category:
                    category_name = re.sub(r'-', '_', category.group(1))
                    category_id = category.group(2)
                    filter_id = category.group(3) or ''

                    filename = '{}_{}'.format(category_name, category_id)
                    if filter_id:
                        filename = '{}_{}'.format(filename, filter_id)

                    with open(self.get_file_path_for_result('{}.csv'.format(filename)), 'w') as item_urls_file:
                        item_urls_writer = csv.writer(item_urls_file)

                        for item_url in self._export_item_urls(category_id, filter_id, exclude):
                            item_urls_writer.writerow([item_url])
                else:
                    raise SitemapSpiderError('Wrong url format: {}'.format(shelf_url))
            except:
                self.logger.error('Cannot process url: {}'.format(traceback.format_exc()))
                failed_urls.append(shelf_url)
        if failed_urls:
            self.save_failed_urls(failed_urls)
            raise SitemapSpiderError('Some urls cannot be processed')

    def _export_item_urls(self, category_id, filter_id, exclude):
        offset = 0
        max_retry_count = 10
        retry_count = 0

        api_url = self.API_URL_TEMPLATE.format(offset=offset,
                                               category_id=category_id,
                                               filter_id=filter_id)

        while True:
            response = None

            try:
                self.logger.debug('Request API: {}'.format(api_url))
                response = requests.get(api_url, headers={'User-Agent': ''})
                response.raise_for_status()

                data = response.json()
                search_response = data.get('search_response')

                if search_response:
                    if exclude:
                        breadcrumbs = search_response.get('breadCrumb_list')

                        if breadcrumbs:
                            breadcrumbs = breadcrumbs[0].get('breadCrumbValues')
                            categories = filter(None, map(lambda x: x.get('categoryId'), breadcrumbs))

                            if set(exclude) & set(categories):
                                self.logger.info('Skip category')
                                return

                    for item in search_response.get('items', {}).get('Item', []):
                        url = item.get('url')
                        if url:
                            yield urljoin(self.domain, url)
                        else:
                            self.logger.warn('Item has not url field: {}'.format(json.dumps(item, indent=2)))

                    meta_data = search_response.get('metaData', [])
                    meta_data = dict((data.get('name'), data.get('value')) for data in meta_data)

                    if int(meta_data.get('currentPage', 0)) < int(meta_data.get('totalPages', 0)):
                        offset += int(meta_data.get('count', 24))
                        api_url = self.API_URL_TEMPLATE.format(offset=offset,
                                                               category_id=category_id,
                                                               filter_id=filter_id)
                        continue
                elif data.get('error_message'):
                    raise Exception(data['error_message'])

                break
            except Exception as e:
                self.logger.error('{}, response {}: {}'.format(e,
                                                               getattr(response, 'status_code', None),
                                                               getattr(response, 'content', None)))
                if retry_count < max_retry_count:
                    retry_count += 1
                    time.sleep(1)
                    self.logger.error('Retry: {}'.format(api_url))
                else:
                    self.logger.error('Max retry times reached: {}'.format(api_url))
                    break


    def task_tcin_to_vendor(self, options):
        missing_options = {'tcins'} - set(options.keys())

        if missing_options:
            raise SitemapSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        tcins = options.get('tcins', [])
        vendors = self._get_vendors(tcins)
        filename = 'tcins'

        with open(self.get_file_path_for_result('{}.csv'.format(filename)), 'w') as tcin_file:
            tcin_writer = csv.writer(tcin_file)
            tcin_writer.writerow(['tcin', 'vendor_id', 'vendor_name', 'relationship_type_code'])

            for tcin, vendor in vendors.iteritems():
                vendor_id = vendor['vendor_id']
                vendor_name = vendor['vendor']
                code = vendor['code']
                tcin_writer.writerow([tcin, vendor_id, vendor_name, code])


    def _get_vendors(self, tcin_list=None):
        # GET VENDOR ID FROM TCIN
        url = "https://api.target.com/digital_items/v1/lite"
        key = "bd932758273956ab88284963312c677c42e394ad"
        headers = {
            'authorization': "Bearer DbLz0cQ1TrTZkSYpl0nc8NojXIZEmRQi",
            'content-type': "application/json",
            'cache-control': "no-cache"
        }
        results = {}

        tcin_request_limit = 100
        for i in range(0, len(tcin_list), tcin_request_limit):
            sub_tcin_list = tcin_list[i:i + tcin_request_limit]

            tcin = ','.join([str(x).strip() for x in sub_tcin_list])

            querystring = {"tcins": tcin, "key": key}

            try:
                response = requests.request("GET", url, headers=headers, params=querystring)

                if response.status_code in [200,206]:
                    json_response = json.loads(response.text)
                    for items in json_response:
                        results[items['tcin']] = {}
                        tcin_obj = results[items['tcin']]
                        
                        tcin_obj['brand'] = items.get('product_brand', {}).get('brand', '')

                        # CHECK IF PRIMARY VENDOR
                        primary_vendor = self._get_primary_vendor(items.get('product_vendors', None))
                        tcin_obj['vendor_id'], tcin_obj['vendor'] = primary_vendor if primary_vendor else ('', '')

                        tcin_obj['code'] = items.get('relationship_type_code', '')
                        if tcin_obj['code'] == 'COP':
                            # IF relationship_type_code is 'COP', this means that it is a Collection item, which doesn't have a Vendor Associated to it.
                            tcin_obj['vendor_id'] = ''
                        elif tcin_obj['code'] in ('VAP', 'VPC'):
                            # If VAP or VPC is present and no vendor ID/Name is provided, use vendor of first child
                            if not tcin_obj['vendor_id']:
                                try:
                                    child_items = items['child_items']
                                    querystring = {"tcins": child_items[0]['tcin'], "key": key}
                                    response = requests.request("GET", url, headers=headers, params=querystring)
                                    response = json.loads(response.text)
                                    primary_vendor = self._get_primary_vendor(response[0].get('product_vendors', None))
                                    tcin_obj['vendor_id'], tcin_obj['vendor'] = primary_vendor if primary_vendor else ('', '')
                                except:
                                    self.logger.error("Exception for tcins {}: {}".format(tcin, traceback.format_exc()))

                        tcin_obj['status'] = items.get('estore_item_status', '')
                else:
                    self.logger.error("Error response received for:"+tcin)
                    self.logger.error("Error code: "+str(response.status_code))
                
            except:
                self.logger.error("Exception for tcins {}: {}".format(tcin, traceback.format_exc()))

        noresponse_tcin_list = [x for x in tcin_list if x not in results.keys()]
        if noresponse_tcin_list:
            self.logger.error("Invalid TCINs in request. No response received for :"+', '.join(noresponse_tcin_list))

        return results


    def _get_primary_vendor(self, vendor_list):
        if not vendor_list:
            return None
        for vendor in vendor_list:
            # Check for primary vendor, and return primary vendor id
            if vendor.get('is_primary_vendor'):
                return vendor.get('id', ''), vendor.get('vendor_name', '')

        # If no primary vendor is present, return first vendor id
        return vendor_list[0].get('id', ''), vendor_list[0].get('vendor_name', '')
