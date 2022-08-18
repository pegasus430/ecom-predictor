import json
import time
from datetime import datetime

from openpyxl import load_workbook


class AmazonTemplateToJSON(object):

    def __init__(self, input_file):
        self.template = input_file
        self.output_type = 'application/json'
        self.output_ext = '.json'

    def convert(self):
        current_time = time.time()
        current_dt = datetime.fromtimestamp(current_time)

        feed = {
            'version': 'RC.1',
            'header': {
                'document_identification': {
                    'reference_key': 'com.cai.feed.{:.2f}'.format(current_time),
                    'created_datetime': current_dt.isoformat() + 'Z'
                }
            },
            'records': self._parse_records()
        }

        return json.dumps(feed, indent=2)

    def _parse_records(self):
        records = []

        wb = load_workbook(self.template, read_only=True)
        ws = wb.active

        rows = ws.rows

        rows.next()  # type
        names = [h.value for h in rows.next()]
        rows.next()  # description
        rows.next()  # name

        for row in rows:
            values = [cell.value for cell in row]

            if any(values):
                record = {
                    'identifier': row[0].value,  # vendor_sku
                    'operation': {
                        'type': 'PARTIAL'
                    },
                    'attributes': self._parse_attributes(names, values, 'TOYS_AND_GAMES')  # TODO: category = sheet name
                }

                records.append(record)

        return records

    def _parse_attributes(self, names, values, category):
        attributes = {
            'product_type': category
        }

        value_index = 0

        for name in names:
            # skip merged cells
            if not name:
                continue

            # skip empty attributes
            if not values[value_index]:
                value_index += 1
                continue

            if name in ('vendor_sku', 'rtip_product_description', 'model_number', 'part_number',
                        'product_category_subcategory', 'country_of_origin', 'telling_page_indicator'):
                # string value
                attributes[name] = {
                    'value': str(values[value_index])
                }
                value_index += 1
            elif name in ('number_of_items', 'rtip_items_per_inner_pack', 'number_of_boxes',
                          'manufacturer_minimum_age', 'manufacturer_maximum_age', ):
                # number value
                attributes[name] = {
                    'value': self._parse_number(values[value_index])
                }
                value_index += 1
            elif name in ('item_name', 'item_type_name', 'color', 'manufacturer', 'brand', 'model_name',
                          'import_designation'):
                # string value with language tag
                attributes[name] = {
                    'language_tag::es_US': {
                        'value': str(values[value_index])
                    }
                }
                value_index += 1
            elif name in ('cost_price',):
                # price value
                attributes[name] = {
                    'currency::USD': {
                        'value': self._parse_number(values[value_index])
                    }
                }
                value_index += 1
            elif name in ('included_components', 'bullet_point', 'generic_keyword', 'target_audience_keyword'):
                # array of string values with language tag
                attributes[name] = {
                    'language_tag::es_US': [
                        {'value': value.strip()} for value in str(values[value_index]).split(',')
                    ]
                }
                value_index += 1
            elif name in ('street_date', 'product_site_launch_date'):
                # date value
                attributes[name] = {
                    'value': self._parse_datetime(values[value_index])
                }
                value_index += 1
            elif name in ('batteries_required', 'is_assembly_required'):
                # boolean value
                attributes[name] = {
                    'value': self._parse_bool(values[value_index])
                }
                value_index += 1
            elif name in ('item_package_weight',):
                # number value with unit
                attributes[name] = {
                    'value': self._parse_number(values[value_index]),
                    'unit': values[value_index + 1]
                }
                value_index += 2
            elif name in ('item_dimensions', 'item_package_dimensions'):
                # dimensions
                attributes[name] = {
                    'length': {
                        'value': self._parse_number(values[value_index]),
                        'unit': values[value_index + 1]
                    },
                    'width': {
                        'value': self._parse_number(values[value_index + 2]),
                        'unit': values[value_index + 3]
                    },
                    'height': {
                        'value': self._parse_number(values[value_index + 4]),
                        'unit': values[value_index + 5]
                    }
                }
                value_index += 6
            elif name in ('external_product_id',):
                # string value with type
                attributes[name] = {
                    'value': str(values[value_index]),
                }
                if values[value_index + 1]:
                    attributes[name]['type'] = str(values[value_index + 1])  # optional
                value_index += 2
            elif name in ('supplier_declared_dg_hz_regulation',):
                # array of string values
                attributes[name] = [
                    {'value': str(value)} for value in values[value_index:value_index + 4] if value
                ]
                value_index += 4
            elif name in ('cpsia_cautionary_statement',):
                # array of string values
                attributes[name] = [
                    {'value': str(value)} for value in values[value_index:value_index + 7] if value
                ]
                value_index += 7
            else:
                value_index += 1

        return attributes

    def _parse_bool(self, value):
        return value.lower() == 'yes'

    def _parse_number(self, value):
        if isinstance(value, basestring):
            try:
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except:
                pass

        return value

    def _parse_datetime(self, value):
        if isinstance(value, basestring):
            value += 'T00:00:00Z'
        elif isinstance(value, datetime):
            value = value.isoformat() + 'Z'

        return value
