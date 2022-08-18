import re
import sys
import operator
from api_lib import *
from pprint import pprint
import xml.etree.ElementTree as ET

tags_map = {
    'Product_Description': 'description',
    'Directions': 'usage_directions',
    'Warnings': 'caution_warnings_allergens',
    # 'Barcode': 'id_value',
}

view_map = {
    'Front': 1,
    'Right': 2,
    '3/4 Right': 2,
    'Left': 3,
    '3/4 Left': 3,
    'Top': 4,
    'Top Down': 5,
    'Back': 6,
    'Bottom': 7,
    'Nutritional Label': 8,
    'Ingredients': 9,
    'Marketing': 10,
    'Barcode': 11,
    'Flat': 12,
    'Logo': 13
}

angle_map = {
    'CENTER': 1,
    'RIGHT': 2,
    'LEFT': 3
}

def get_order(image):
    return (view_map.get(image.get('view'), max(view_map.values()) + 1)) * (max(angle_map.values()) + 1) + \
            angle_map.get(image.get('angle'), max(angle_map.values()) + 1)


def setup_parse(content, dest, api_key, token, customer):
    products = ET.fromstring(content)

    if not (products.tag == 'products' and products[0].tag == 'header'):
        message = 'expected structure &lt;products&gt;&lt;header&gt;'
        raise ValueError(message)
    report_status(api_key, token, 2, dest)
    parse(products, dest, api_key, token, customer)


def parse(products, dest, api_key, token, customer):
    products_json = []
    product_count = 0
    for product in products:
        if product.tag == 'header':
            continue
        product_json = {'id_type': 'upc'}
        shelf_description_list = []
        in_pack_images = {}
        out_of_pack_images = {}
        multiple_out_of_pack_images = {}
        secondary_images = {}
        other_images = {}

        try:
            for field in product:
                if field.tag in tags_map:
                    field_name = tags_map[field.tag]
                    if field.text == 'Not Available':
                        continue
                    product_json[field_name] = field.text

                if field.tag == 'Barcode':
                    product_json['id_value'] = field.text.zfill(12)[-12:]

                if field.tag == 'Product_Title_Long':
                    product_json['product_name'] = field.text
                if field.tag == 'Categoy':
                    product_json['category'] = {'name': field.text}
                if field.tag == 'Ingredients' and field.text:
                    product_json['ingredients'] = field.text.split(', ')

                if field.tag == 'images':
                    if 'images' not in product_json:
                        product_json['images'] = {}

                    for image in field.findall('image'):
                        image_url = image.find('url').text
                        asset_subtype = image.get('asset_subtype')
                        if asset_subtype == 'In Package':
                            in_pack_images[image_url] = get_order(image)
                        elif asset_subtype == 'Out of Package':
                            out_of_pack_images[image_url] = get_order(image)
                        elif asset_subtype == 'Multiple Products Out of Pack':
                            multiple_out_of_pack_images[image_url] = get_order(image)
                        elif asset_subtype == 'Secondary Image':
                            num = re.search('(\d+)([^\w]|$)', image_url.split('/')[-1])
                            if num:
                                secondary_images[image_url] = int(num.group(1))
                            else:
                                secondary_images[image_url] = sys.maxint
                        else:
                            other_images[image_url] = get_order(image)

                    for image_pair in sorted(in_pack_images.items(), key=operator.itemgetter(1)):
                        product_json['images'][image_pair[0]] = len(product_json['images']) + 1
                    for image_pair in sorted(out_of_pack_images.items(), key=operator.itemgetter(1)):
                        product_json['images'][image_pair[0]] = len(product_json['images']) + 1
                    for image_pair in sorted(multiple_out_of_pack_images.items(), key=operator.itemgetter(1)):
                        product_json['images'][image_pair[0]] = len(product_json['images']) + 1
                    for image_pair in sorted(secondary_images.items(), key=operator.itemgetter(1)):
                        product_json['images'][image_pair[0]] = len(product_json['images']) + 1
                    for image_pair in sorted(other_images.items(), key=operator.itemgetter(1)):
                        product_json['images'][image_pair[0]] = len(product_json['images']) + 1

                    # DEBUG
                    '''
                    if product_json['id_value'] == '069055862179':
                        for k, v in product_json['images'].iteritems():
                            print k, v
                            for image in field.findall('image'):
                                image_url = image.find('url').text
                                if image_url == k:
                                    print ET.tostring(image)
                    '''

                if field.tag == 'Product_Description':
                    product_json['description'] = field.text

                if 'Features_and_Benefits' in field.tag and field.text:
                    if customer == 'jet.com':
                        if 'bullets' not in product_json:
                            product_json['bullets'] = []
                        product_json['bullets'].append(field.text)
                    else:
                        if 'long_description' not in product_json:
                            product_json['long_description'] = '<ul>'
                        product_json['long_description'] += '<li>' + field.text + '</li>'

                        if len(shelf_description_list) < 2:
                            shelf_description_list.append(field.text)
        except:
            print traceback.format_exc()

        if not product_json.get('id_value'):
            pprint(product_json)
        else:
            print product_json['id_value']

            with open('all_pg_upcs.csv', 'a') as f:
                f.write(product_json['id_value'] + '\n')

        if product_json.get('long_description'):
            product_json['long_description'] += '</ul>'

        if shelf_description_list:
            product_json['shelf_description'] = '<ul><li>' + '</li><li>'.join(shelf_description_list) + '</li></ul>'

        products_json.append(product_json)
        product_count += 1

    print 'PRODUCT_COUNT', product_count

    i = 0
    while i < len(products_json):
        token, result = send_json(api_key, token, products_json[i: i + 500], dest)
        for upc, msgs in result.get('error_log', {}).iteritems():
            if 'Product not found in Master Catalog.' in msgs:
                with open('missing_pg_upcs.csv', 'a') as f:
                    f.write(upc + '\n')
        i += 500

    report_status(api_key, token, 3, dest)

if __name__ == '__main__':
    parse(sys.argv[1], sys.argv[2], None)
