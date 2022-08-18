import traceback
import json
from datetime import datetime
from urlparse import urlparse

import requests
import jinja2
import os
import lxml.html
import sys

from . import SubmissionSpider, SubmissionSpiderError


class WalmartSubmissionSpider(SubmissionSpider):
    retailer = 'walmart.com'
    driver_engine = None  # don't use web driver

    bucket_name = 'walmart-submissions'

    endpoint_credentials = ('root', """AR"M2MmQ+}s9'TgH""")

    feed_item_limit = 50

    def __init__(self, *args, **kwargs):
        super(WalmartSubmissionSpider, self).__init__(*args, **kwargs)

        self.fields = {}
        self.categories = {}
        self.category_attributes = {}

        self.versions = {
            '1.4.1': {
                'send': {
                    'endpoint': 'http://restapis.contentanalyticsinc.com:8080/items_update_with_xml_file_by_walmart_api/',
                    'request_url': 'https://marketplace.walmartapis.com/v2/feeds?feedType=item',
                },
                'check': {
                    'endpoint': 'http://restapis.contentanalyticsinc.com:8080/check_feed_status_by_walmart_api/',
                    'request_url': 'https://marketplace.walmartapis.com/v2/feeds/{feedId}?includeDetails=true'
                }
            },
            '3.1': {
                'send': {
                    'options': {'consumer_id', 'private_key'},
                    'endpoint': 'http://restapis-itemsetup.contentanalyticsinc.com:8080/items_update_with_xml_file_by_walmart_api/',
                    'request_url': 'https://marketplace.walmartapis.com/v3/feeds?feedType=SUPPLIER_FULL_ITEM',
                },
                'check': {
                    'endpoint': 'http://restapis-itemsetup.contentanalyticsinc.com:8080/check_feed_status_by_walmart_api/',
                    'request_url': 'https://marketplace.walmartapis.com/v3/feeds/{feedId}?includeDetails=true'
                }
            }
        }

    def task_content(self, options, products, server, **kwargs):
        version = options.get('version')
        if not version:
            raise SubmissionSpiderError('Missing option: version')

        if version not in self.versions:
            raise SubmissionSpiderError('Not supporting version: {}. Allowed values: {}'.format(
                version,
                ', '.join(self.versions.keys())
            ))

        missing_options = self.versions[version].get('send', {}).get('options', set()) - set(options)
        if missing_options:
            raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        escaped_version = version.replace('.', '_')

        xml_template = self._get_xml_template(escaped_version)
        if not xml_template:
            raise SubmissionSpiderError('Template was not found for version {}'.format(version))

        get_xml_products = getattr(self, '_get_xml_products_{}'.format(escaped_version), None)
        if not callable(get_xml_products):
            raise SubmissionSpiderError('Products generator was not found for version {}'.format(version))

        item_limit = options.get('item_limit', self.feed_item_limit)
        if item_limit:
            try:
                item_limit = abs(int(item_limit))
            except:
                item_limit = self.feed_item_limit
        else:
            item_limit = sys.maxint

        xml_feeds = []

        for i in range(0, len(products), item_limit):
            limit_products = products[i:i + item_limit]

            xml_feed = self.get_file_path_for_result('feed_{}.xml'.format(i / item_limit + 1))

            xml_template.stream(products=get_xml_products(limit_products,
                                                          server,
                                                          fields_filter=options.get('fields_only')),
                                fields=options.get('fields_only')).dump(xml_feed)

            xml_feeds.append(xml_feed)

        if not self.sandbox and options.get('do_submit'):
            self._send_xml_feeds(version,
                                 xml_feeds,
                                 self._get_server_name(server),
                                 options)

    def _get_xml_template(self, version):
        template_loader = jinja2.FileSystemLoader(searchpath=os.path.join(os.getcwd(), 'app', 'templates'))
        template_env = jinja2.Environment(loader=template_loader, trim_blocks=True, lstrip_blocks=True)
        template_env.filters.update({
            'is_list': lambda x: isinstance(x, list),
        })

        return template_env.get_template('walmart/{}.xml'.format(version))

    def _get_xml_products_1_4_1(self, products, server, fields_filter=None):
        for product in products:
            common_attributes = (product.get('attributes') or {}).get('common') or {}
            category_attributes = (product.get('attributes') or {}).get('category') or {}

            if not category_attributes.get('brand'):
                category_attributes['brand'] = product.get('brand')

            xml_product = {
                'product_name': u'<![CDATA[{}]]>'.format(product['product_name'])
                if product.get('product_name') else '',

                'long_description': u'<![CDATA[{}]]>'.format(product['long_description'])
                if product.get('long_description') else '',

                'shelf_description': u'<![CDATA[{}]]>'.format(product['shelf_description'])
                if product.get('shelf_description') else '',

                'short_description': u'<![CDATA[{}]]>'.format(product['description'])
                if product.get('description') else '',

                'upc': product.get('upc') or '',
                'units_per_consumer_unit': common_attributes.get('unitsPerConsumerUnit') or 1,
                'country_of_origin_assembly': common_attributes.get('countryOfOriginAssembly') or 'CN',
                'country_of_origin_components': common_attributes.get('countryOfOriginComponents')
                                                or 'USA and Imported',
                'is_aerosol': self._bool_to_str(common_attributes.get('isAerosol') or False),
                'is_chemical': self._bool_to_str(common_attributes.get('isChemical') or False),
                'is_pesticide': self._bool_to_str(common_attributes.get('isPesticide') or False),
                'has_batteries': self._bool_to_str(common_attributes.get('hasBatteries') or False),
                'contains_mercury': self._bool_to_str(common_attributes.get('containsMercury') or False),
                'has_fuel_container': self._bool_to_str(common_attributes.get('hasFuelContainer') or False),
                'price_per_unit_quantity': {
                    'unit': common_attributes.get('pricePerUnitQuantityMeasure') or 'Each',
                    'measure': common_attributes.get('pricePerUnitQuantity') or 1
                },
                'contains_paper_wood': self._bool_to_str(common_attributes.get('containsPaperWood') or False),
                'composite_wood_certification_code': common_attributes.get('compositeWoodCertificationCode') or 1,
                'has_expiration': self._bool_to_str(common_attributes.get('hasExpiration') or False),
                'has_warnings': self._bool_to_str(common_attributes.get('hasWarnings') or False),
                'has_warranty': self._bool_to_str(common_attributes.get('hasWarranty') or False),
                'is_prop_65_warning_required':
                    self._bool_to_str(common_attributes.get('isProp65WarningRequired') or False),
                'is_temperature_sensitive': self._bool_to_str(common_attributes.get('isTemperatureSensitive') or False),
                'small_parts_warning': common_attributes.get('smallPartsWarnings') or 0,
                'is_controlled_substance': self._bool_to_str(common_attributes.get('isControlledSubstance') or False),
                'has_state_restrictions': self._bool_to_str(common_attributes.get('hasStateRestrictions') or False)
            }

            if product.get('caution_warnings_allergens'):
                xml_product['has_warnings'] = self._bool_to_str(True)
                xml_product['warning_text'] = u'<![CDATA[{}]]>'.format(product['caution_warnings_allergens'])

            if product.get('customer_id') and (product.get('usage_directions') or product.get('ingredients')):
                xml_product['additional_product_attributes'] = []

                fields = self._get_fields_from_customer_settings(server, product['customer_id'])

                if product.get('usage_directions') and self._str_to_bool(fields.get('usage_directions')):
                    xml_product['additional_product_attributes'].append({
                        'name': 'instructions',
                        'value': u'<![CDATA[{}]]>'.format(self._strip_tags(product['usage_directions']))
                    })

                if product.get('ingredients') and self._str_to_bool(fields.get('ingredients')):
                    xml_product['additional_product_attributes'].append({
                        'name': 'ingredients',
                        'value': u'<![CDATA[{}]]>'.format(self._strip_tags(product['ingredients']))
                    })

            images = product.get('image_urls')

            if images:
                xml_product['main_image'] = images[0]
                xml_product['additional_assets'] = images[1:]

            if product.get('category_id') and product.get('category_name'):
                xml_product['category_name'] = product['category_name']
                xml_product['category_attributes'] = self._get_category_attributes(server,
                                                                                   product,
                                                                                   category_attributes)

            yield xml_product

    def _get_fields_from_customer_settings(self, server, customer_id):
        if customer_id in self.fields:
            return self.fields[customer_id]

        url = '{server}/api/settings/mc/customers/{customer_id}?api_key={api_key}'.format(
            server=server['url'],
            api_key=server['api_key'],
            customer_id=customer_id
        )

        try:
            self.logger.info('Loading customer {} fields: {}'.format(customer_id, url))
            response = requests.get(url).json()

            fields = json.loads(response.get('fields'))
        except:
            self.logger.error('Could not load customer {} fields: {}'.format(customer_id, traceback.format_exc()))
            fields = {}

        self.fields[customer_id] = fields

        return fields

    def _strip_tags(self, text):
        return lxml.html.fromstring(text).text_content()

    def _get_category_attributes(self, server, product, category_attributes):
        required_only = int(product.get('view_type') or 0) != 2

        result_attributes = []

        try:
            if product['category_id'] in self.category_attributes:
                response = self.category_attributes[product['category_id']]
            else:
                url = '{server}/api/category/{category_id}/attributes?api_key={api_key}'.format(
                    server=server['url'],
                    api_key=server['api_key'],
                    category_id=product['category_id']
                )

                self.logger.info('Loading category {} attributes: {}'.format(product['category_id'], url))
                response = requests.get(url).json()

                self.category_attributes[product['category_id']] = response

            result_attributes = self._prepare_attributes(required_only, category_attributes, response)
        except:
            self.logger.error('Could not load category {} attributes: {}'.format(product['category_id'],
                                                                                 traceback.format_exc()))

        return result_attributes

    def _prepare_attributes(self, required_only, category_attributes, attributes):
        prepared_attributes = []

        for attribute in attributes:
            if required_only:
                if not self._str_to_bool(attribute.get('visible')) or int(
                                attribute.get('min_occurs') or 0) != 1:
                    continue

            attribute_name = attribute.get('name')
            prepared_attribute = {'name': attribute_name}

            if attribute.get('subattributes'):
                prepared_attribute['value'] = self._prepare_attributes(
                    required_only,
                    category_attributes.get(attribute_name) or {},
                    attribute['subattributes'])
            else:
                prepared_attribute['value'] = self._get_category_attribute_value(attribute, category_attributes)

            # TODO: attribute assets

            prepared_attributes.append(prepared_attribute)

        return prepared_attributes

    def _get_category_attribute_value(self, attribute, category_attributes):
        attribute_name = attribute.get('name')
        attribute_type = int(attribute.get('type') or 0)
        attribute_default = attribute.get('default_value')

        if attribute_type == 1:
            # bool
            if category_attributes.get(attribute_name) is not None:
                return self._bool_to_str(self._str_to_bool(category_attributes[attribute_name]))
            elif attribute_default:
                return self._bool_to_str(self._str_to_bool(attribute_default))
            else:
                return self._bool_to_str(False)
        elif attribute_type == 2:
            # string
            if category_attributes.get(attribute_name) is not None:
                return category_attributes[attribute_name]
            elif attribute_default:
                return attribute_default
            else:
                return ''
        elif attribute_type == 3:
            # enum
            if category_attributes.get(attribute_name):
                if self._str_to_bool(attribute.get('multiple_values')):
                    return map(lambda x: {'name': '{}Value'.format(attribute_name), 'value': x},
                               category_attributes[attribute_name].values())
                else:
                    return category_attributes[attribute_name]
            elif attribute_default:
                return attribute_default
            else:
                return ''
        elif attribute_type == 4:
            # int
            if category_attributes.get(attribute_name) is not None:
                return str(category_attributes[attribute_name])
            elif attribute_default:
                return str(attribute_default)
            else:
                return ''
        else:
            self.logger.warn('Unknown attribute type: {}'.format(attribute))
            return ''

    def _bool_to_str(self, value):
        return str(value).lower()

    def _str_to_bool(self, value):
        if value is None:
            return False

        if isinstance(value, bool):
            return value

        value = str(value).strip().lower()

        if value in ['false', 'f', 'no', 'n', 'off', 'disable', 'disabled']:
            return False
        elif value in ['true', 't', 'yes', 'y', 'on', 'enable', 'enabled']:
            return True
        else:
            try:
                return bool(int(value))
            except:
                self.logger.warn('Unknown value: {}, {}'.format(value, traceback.format_exc()))
                return False

    def _get_xml_products_3_1(self, products, server, fields_filter=None):
        for product in products:
            if not product.get('category_id') or not product.get('category_name'):
                self.logger.warn('Product {} has not category'.format(product.get('id')))
                continue

            category_attributes = (product.get('attributes') or {}).get('category') or {}

            if not category_attributes.get('brand'):
                category_attributes['brand'] = product.get('brand')
            else:
                product['brand'] = category_attributes['brand']

            xml_product = {
                'sku': product.get('upc') or '',
                'product_name': u'<![CDATA[{}]]>'.format(product['product_name'])
                if product.get('product_name') else '',

                'product_id': product.get('upc') or '',
                'additional_product_attributes': [],
                'category': product.get('category_name'),
                'short_description': u'<![CDATA[{}]]>'.format(product['description'])
                if product.get('description') else '',

                'key_features_value': u'<![CDATA[{}]]>'.format(product['long_description'])
                if product.get('long_description') else ''
            }

            if product.get('shelf_description'):
                if not fields_filter or 'shelf_description' in fields_filter:
                    xml_product['additional_product_attributes'].append({
                        'name': 'shelf_description',
                        'value': u'<![CDATA[{}]]>'.format(product['shelf_description'])
                    })

            if product.get('usage_directions'):
                if not fields_filter or 'usage_directions' in fields_filter:
                    xml_product['additional_product_attributes'].append({
                        'name': 'instructions',
                        'value': u'<![CDATA[{}]]>'.format(product['usage_directions'])
                    })

            if product.get('ingredients'):
                if not fields_filter or 'ingredients' in fields_filter:
                    xml_product['additional_product_attributes'].append({
                        'name': 'ingredients',
                        'value': u'<![CDATA[{}]]>'.format(product['ingredients'])
                    })

            if product.get('caution_warnings_allergens'):
                if not fields_filter or 'caution_warnings_allergens' in fields_filter:
                    xml_product['additional_product_attributes'].append({
                        'name': 'warning text',
                        'value': u'<![CDATA[{}]]>'.format(product['caution_warnings_allergens'])
                    })

            if product.get('parent_category_id'):
                xml_product['parent_category'] = self._get_category_name(server, product['parent_category_id'])

            images = product.get('image_urls')

            if images:
                xml_product['main_image'] = images[0]
                xml_product['secondary_images'] = images[1:]

            yield xml_product

    def _get_category_name(self, server, category_id):
        if category_id in self.categories:
            return self.categories[category_id]

        url = '{server}/api/category/{category_id}?api_key={api_key}'.format(
            server=server['url'],
            api_key=server['api_key'],
            category_id=category_id
        )

        try:
            self.logger.info('Loading category {}: {}'.format(category_id, url))
            response = requests.get(url).json()

            category_name = response.get('name')

            self.categories[category_id] = category_name

            return category_name
        except:
            self.logger.error('Could not load category {}: {}'.format(category_id, traceback.format_exc()))

    def task_rich_media(self, options, products, server, **kwargs):
        xml_template = self._get_xml_template('rich_media')
        if not xml_template:
            raise SubmissionSpiderError('Template was not found for rich media')

        get_xml_products = getattr(self, '_get_xml_products_rich_media', None)
        if not callable(get_xml_products):
            raise SubmissionSpiderError('Products generator was not found for rich media')

        item_limit = options.get('item_limit', self.feed_item_limit)
        if item_limit:
            try:
                item_limit = abs(int(item_limit))
            except:
                item_limit = self.feed_item_limit
        else:
            item_limit = sys.maxint

        xml_feeds = []

        for i in range(0, len(products), item_limit):
            limit_products = products[i:i + item_limit]

            xml_feed = self.get_file_path_for_result('feed_{}.xml'.format(i / item_limit + 1))

            xml_template.stream(products=get_xml_products(limit_products, server),
                                feed_date=datetime.now().strftime('%Y-%m-%dT%H:%M:%S')).dump(xml_feed)

            xml_feeds.append(xml_feed)

        if not self.sandbox and options.get('do_submit'):
            self._send_xml_feeds('1.4.1',
                                 xml_feeds,
                                 self._get_server_name(server),
                                 options)

    def _get_server_name(self, server):
        server_url = server.get('url', '')
        server_url_parts = urlparse(server_url)
        server_name = server_url_parts.netloc.split('.')[0]

        if not server_name:
            raise SubmissionSpiderError('Server name is empty')

        return server_name

    def _get_xml_products_rich_media(self, products, server, fields_filter=None):
        for product in products:
            if not product.get('videos'):
                self.logger.warn('Product {} has not videos'.format(product.get('id')))
                continue

            xml_product = {
                'product_id': product.get('upc') or '',
                'short_description': product.get('description') or '',
                'videos': []
            }

            for video in product['videos']:
                xml_video = {
                    'provider': product.get('brand_attribute') or '',
                    'title': (product.get('product_name') or '')[:50],
                    'url': video.get('video_url') or '',
                    'width': video.get('width') or 0,
                    'height': video.get('height') or 0,
                    'format': os.path.splitext(video.get('') or '')[-1][1:],
                    'duration': video.get('duration') or 0
                }

                if video.get('thumbnails'):
                    thumbnail = video['thumbnails'][0]

                    xml_video['thumbnail_url'] = thumbnail.get('url') or ''
                    xml_video['thumbnail_width'] = thumbnail.get('width') or 0
                    xml_video['thumbnail_height'] = thumbnail.get('height') or 0

                xml_product['videos'].append(xml_video)

            yield xml_product

    def _send_xml_feeds(self, version, xml_feeds, server_name, options):
        request_data = self.versions.get(version, {}).get('send')

        request_options = request_data.get('options')
        request_endpoint = request_data.get('endpoint')
        request_url = request_data.get('request_url')

        data = {
            'request_method': 'POST',
            'server_name': server_name,
            'request_url': request_url
        }

        if request_options:
            data.update({option: options[option] for option in request_options})

        self.logger.info('Sending XML {} with data {} to {}'.format(xml_feeds, data, request_endpoint))

        files = [('xml_file_to_upload', open(xml_feed, 'rb')) for xml_feed in xml_feeds]

        try:
            response = requests.post(request_endpoint,
                                     data=data,
                                     files=files,
                                     auth=self.endpoint_credentials)

            self.logger.debug('Response {}: {}'.format(response.status_code, response.content))

            response.raise_for_status()

            response_data = response.json()
        except:
            self.logger.error('Could not send XML: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Sending failed')
        else:
            for group_name, group_data in response_data.iteritems():
                error = group_data.get('error') \
                        or group_data.get('ns2:errors', {}).get('ns2:error', {}).get('ns2:description')

                if error:
                    raise SubmissionSpiderError('{}: {}'.format(group_name, error))

                feed_id = group_data.get('feedId') or group_data.get('ns2:FeedAcknowledgement', {}).get('ns2:feedId')

                if feed_id:
                    self.data.setdefault('feeds', []).append(feed_id)
                    self.async_check_required = True

                    self.logger.info('{}: XML feed {} was sent successfully'.format(group_name, feed_id))
                else:
                    raise SubmissionSpiderError('{}: Unknown feed id'.format(group_name))

    def task_check(self, options, **kwargs):
        feeds = options.get('feeds', [])

        if not feeds:
            feed_id = options.get('feed_id')

            if feed_id:
                feeds = [feed_id]

        if not feeds:
            raise SubmissionSpiderError('There are not feeds for check')

        version = options.get('version', '1.4.1')

        request_data = self.versions.get(version, {}).get('check')

        request_endpoint = request_data.get('endpoint')
        request_url = request_data.get('request_url')

        data = {}

        for i, feed_id in enumerate(feeds):
            group_name = 'feed_{}'.format(i)

            data['feed_id_{}'.format(group_name)] = feed_id
            data['request_url_{}'.format(group_name)] = request_url

        self.logger.info('Requesting feeds {} status with data {} from {}'.format(feeds, data, request_endpoint))

        try:
            response = requests.post(request_endpoint,
                                     data=data,
                                     auth=self.endpoint_credentials)

            self.logger.debug('Response {}: {}'.format(response.status_code, response.content))

            response.raise_for_status()

            response_data = response.json()
        except:
            self.logger.error('Could not check status: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Status checking failed')
        else:
            response_data.pop('feed_id', None)

            for group_name, group_data in response_data.iteritems():
                error = group_data.get('error') \
                        or group_data.get('ns2:errors', {}).get('ns2:error', {}).get('ns2:description')

                if error:
                    raise SubmissionSpiderError('{}: {}'.format(group_name, error))

                self.data[group_name] = group_data

                feed_status = group_data.get('feedStatus')

                if feed_status == 'PROCESSED':
                    self.async_check_required = False

                    self.logger.info('{}: Feed was processed'.format(group_name))
                elif feed_status == 'ERROR':
                    raise SubmissionSpiderError('{}: Feed was not processed'.format(group_name))
                else:
                    self.async_check_required = True
