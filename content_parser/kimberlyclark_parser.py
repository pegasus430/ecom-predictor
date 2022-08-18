import re
import traceback
from api_lib import *
from pprint import pprint
import xml.etree.ElementTree as ET

def setup_parse(content, dest, api_key, token, customer):
    products = ET.fromstring(content).find('Products')

    if not products:
        message = 'Couldn\'t find <Products>'
        raise ValueError(message)

    report_status(api_key, token, 2, dest)

    parse(products, dest, api_key, token, customer)

def parse(products, dest, api_key, token, customer):
    try:
        product_count = 0
        products_json = []

        for product in products:
            product_json = {}

            features = {}
            amazon_features = {}
            walmart_features = {}

            product_title = None
            description = None

            product_json['id_type'] = 'upc'

            try:
                values = product.find('Values')

                if values:
                    for value in values.findall('Value') + values.findall('MultiValue'):

                        # ID value
                        if value.get('AttributeID') == 'EACH_UPC':
                            product_json['id_value'] = value.text.zfill(12)[-12:]

                        # Default values for product_title, description, and features
                        if value.get('AttributeID') == 'PRODUCT_TITLE':
                            product_title = value.text

                        if value.get('AttributeID') == 'DESCRIPTION':
                            description = value.text

                        feature_match = re.match('FEATURE_(\d+)', value.get('AttributeID', ''))

                        if feature_match and value.text:
                            feature_no = int(feature_match.group(1))
                            features[feature_no] = value.text

                        # Walmart
                        if customer == 'Walmart.com':
                            if value.get('AttributeID') == 'WALMART_PRODUCT_TITLE':
                                product_json['product_name'] = value.text

                            if value.get('AttributeID') == 'WALMART_DESCRIPTION' and value.text.strip():
                                product_json['description'] = value.text

                            feature_match = re.match('WALMART_FEATURE_(\d+)', value.get('AttributeID', ''))

                            if feature_match and value.text:
                                feature_no = int(feature_match.group(1))
                                walmart_features[feature_no] = value.text

                            if value.get('AttributeID') == 'WALMART_SEARCH_DESCRIPTION' and value.text.strip():
                                product_json['shelf_description'] = value.text

                        # Amazon
                        if customer == 'Amazon.com':
                            if value.get('AttributeID') == 'AMAZON_PRODUCT_TITLE':
                                product_json['product_name'] = value.text

                            feature_match = re.match('AMAZON_FEATURE_(\d+)', value.get('AttributeID', ''))

                            if feature_match and value.text:
                                feature_no = int(feature_match.group(1))
                                amazon_features[feature_no] = value.text

                            if value.get('AttributeID') == 'AMAZON_DESCRIPTION' and value.text.strip():
                                product_json['long_description'] = value.text

                            if value.get('AttributeID') == 'AMAZON_BROWSE_KEYWORD' and value.text.strip():
                                product_json['browse_keywords'] = value.text

                    for asset in product.findall('AssetCrossReference'):
                        if 'images' not in product_json:
                            product_json['images'] = {}

                        if asset.get('AssetID'):
                            img_url = 'https://s3.amazonaws.com/kcc-image/{}.jpg'.format(asset.get('AssetID'))
                            product_json['images'][img_url] = len(product_json['images']) + 1

            except:
                print traceback.format_exc()

            # Sort features
            features = [features[i] for i in sorted(features)]
            amazon_features = [amazon_features[i] for i in sorted(amazon_features)]
            walmart_features = [walmart_features[i] for i in sorted(walmart_features)]

            # Master Data
            if customer == 'Master Data':
                if product_title:
                    product_json['product_name'] = product_title

                if features:
                    product_json['bullets'] = features

                if description:
                    product_json['long_description'] = description

            # Walmart defaults
            if customer == 'Walmart.com':
                if not product_json.get('product_name') and product_title:
                    product_json['product_name'] = product_title
                    # TODO: used default

                if not product_json.get('description') and description:
                    product_json['description'] = description
                    # TODO: used default

                if walmart_features or features:
                    product_json['long_description'] = '<ul>'
                    for feature in walmart_features or features:
                        product_json['long_description'] += '<li>' + feature + '</li>'
                    product_json['long_description'] += '</ul>'

                    if features and not walmart_features:
                        pass
                        # TODO: used default

            # Amazon defaults
            if customer == 'Amazon.com':
                if not product_json.get('product_name') and product_title:
                    product_json['product_name'] = product_title
                    # TODO: used default

                if amazon_features:
                    product_json['bullets'] = amazon_features
                elif features:
                    product_json['bullets'] = features
                    # TODO: used default

                if not product_json.get('long_description') and description:
                    product_json['long_description'] = description
                    # TODO: used default

            #####

            if not product_json.get('id_value'):
                pprint(product_json)
            else:
                print product_json['id_value']

                with open('all_kimberlyclark_upcs.csv', 'a') as f:
                    f.write(product_json['id_value'] + '\n')

            products_json.append(product_json)

            product_count += 1

        print 'PRODUCT_COUNT', product_count

        i = 0

        while i < len(products_json):
            token, result = send_json(api_key, token, products_json[i: i + 500], dest)
            for upc, msgs in result.get('error_log', {}).iteritems():
                if 'Product not found in Master Catalog.' in msgs:
                    with open('missing_kimberlyclark_upcs.csv', 'a') as f:
                        f.write(upc + '\n')
            i += 500

        report_status(api_key, token, 3, dest)
    except:
        print 'ERROR PARSING', traceback.format_exc()

if __name__ == '__main__':
    parse(sys.argv[1], sys.argv[2])
