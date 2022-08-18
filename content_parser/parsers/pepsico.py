import json
import os
import sys
import traceback
from datetime import datetime

import xlrd

from . import Parser

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'various'))
from pepsico_images import PepsiCoImages


class PepsicoParser(Parser):
    company = 'pepsico_allimages'

    def __init__(self, *args, **kwargs):
        super(PepsicoParser, self).__init__(*args, **kwargs)
        self.pepsico_images_filter = None

    def _parse(self, filename):
        workbook = xlrd.open_workbook(filename)

        products = []
        nutrition = list(self._load_products(workbook.sheet_by_name('Nutrition')))
        images = None
        images_dir = None

        try:
            for source_product in self._load_products(workbook.sheet_by_name('Products')):
                product = self._convert_product(source_product)
                if self._import_type in (self.IMPORT_TYPE_IMAGES, self.IMPORT_TYPE_PRODUCTS_AND_IMAGES):
                    if images is None or images_dir is None:
                        images = PepsiCoImages(filename, log=self.logger, images_filter=self.pepsico_images_filter)
                        images_dir = datetime.now().strftime('%Y/%m/%d')
                    product_images = images.download(
                        gtin=source_product.get('gtin'),
                        image_dir=images_dir,
                        bucket='ca-temp-storage'
                    )
                    product['images'] = dict((image['url'], i) for i, image in enumerate(product_images, 1))
                else:
                    product['images'] = {}

                if self.config.get('endpoint', {}).get('customer') == 'Instacart.com':
                    for source_nutrition in nutrition:
                        if source_nutrition.get('gtin') == source_product.get('gtin'):
                            product.setdefault('common', {})['NutritionInformation'] = \
                                self._convert_nutrition(source_nutrition)

                            break

                products.append(product)
        finally:
            if images is not None:
                images._stop_workers()
        return products

    def _convert_product(self, source_product):
        product = {
            'id_type': 'gtin',
            'id_value': source_product.get('gtin', '')
        }
        if self._import_type not in (self.IMPORT_TYPE_PRODUCTS, self.IMPORT_TYPE_PRODUCTS_AND_IMAGES):
            return product

        product['product_name'] = source_product.get('custom_product_name', '')
        product['long_description'] = source_product.get('romance_copy_1', '')
        product['bullets'] = json.dumps(filter(None, [
            source_product.get('why_buy_1'),
            source_product.get('why_buy_2'),
            source_product.get('why_buy_3'),
            source_product.get('why_buy_4'),
            source_product.get('why_buy_5')
        ]))
        product['browse_keyword'] = source_product.get('keywords', '')
        product['ingredients'] = source_product.get('ingredients', '')
        product['caution_warnings_allergens'] = source_product.get('allergens', '')
        product['category'] = {
            'name': 'Master',
            'attributes': {
                'brand': source_product.get('brand_name', '')
            }
        }
        product['common'] = {
            'Size': source_product.get('product_size', ''),
            'UOM': source_product.get('uom', '')
        }

        return product

    def _convert_nutrition(self, source_nutrition):
        nutrition = dict()

        nutrition['calcium_daily_percent'] = source_nutrition.get('dvp_calcium', '')
        nutrition['calories_from_fat_per_serving'] = source_nutrition.get('fat_calories_per_serving', '')
        nutrition['calories_per_serving'] = source_nutrition.get('calories_per_serving', '')
        nutrition['cholesterol_mg'] = self._check_unit_of_measure(
            source_nutrition.get('cholesterol_per_serving', ''),
            source_nutrition.get('cholesterol_uom', ''),
            'MG'
        )
        nutrition['cholesterol_daily_percent'] = source_nutrition.get('dvp_cholesterol', '')
        nutrition['dietary_fiber_g'] = self._check_unit_of_measure(
            source_nutrition.get('fiber_per_serving', ''),
            source_nutrition.get('fiber_uom', ''),
            'G'
        )
        nutrition['dietary_fiber_daily_percent'] = source_nutrition.get('dvp_fiber', '')
        nutrition['iron_daily_percent'] = source_nutrition.get('dvp_iron', '')
        nutrition['monounsaturated_fat_g'] = self._check_unit_of_measure(
            source_nutrition.get('mono_unsat_fat', ''),
            source_nutrition.get('mono_unsat_fat_uom'),
            'G'
        )
        nutrition['polyunsaturated_fat_g'] = self._check_unit_of_measure(
            source_nutrition.get('poly_unsat_fat', ''),
            source_nutrition.get('poly_unsat_fat_uom'),
            'G'
        )
        nutrition['potassium_daily_percent'] = source_nutrition.get('dvp_potassium', '')
        nutrition['potassium_mg'] = self._check_unit_of_measure(
            source_nutrition.get('potassium_per_serving', ''),
            source_nutrition.get('potassium_uom'),
            'MG'
        )
        nutrition['protein_g'] = self._check_unit_of_measure(
            source_nutrition.get('protein_per_serving', ''),
            source_nutrition.get('protein_uom'),
            'G'
        )
        nutrition['saturated_fat_g'] = self._check_unit_of_measure(
            source_nutrition.get('sat_fat_per_serving', ''),
            source_nutrition.get('sat_fat_uom'),
            'G'
        )
        nutrition['saturated_fat_daily_percent'] = source_nutrition.get('dvp_saturated_fat', '')
        nutrition['serving_size'] = source_nutrition.get('serving_size', '')
        nutrition['serving_size_uom'] = source_nutrition.get('serving_size_uom', '')
        nutrition['servings_per_container'] = source_nutrition.get('servings_per_container', '')
        nutrition['sodium_mg'] = self._check_unit_of_measure(
            source_nutrition.get('sodium_per_serving', ''),
            source_nutrition.get('sodium_uom'),
            'MG'
        )
        nutrition['sodium_daily_percent'] = source_nutrition.get('dvp_sodium', '')
        nutrition['total_carbohydrate_g'] = self._check_unit_of_measure(
            source_nutrition.get('carbo_per_serving', ''),
            source_nutrition.get('carbo_uom'),
            'G'
        )
        nutrition['total_carbohydrate_daily_percent'] = source_nutrition.get('dvp_carbo', '')
        nutrition['total_fat_g'] = self._check_unit_of_measure(
            source_nutrition.get('total_fat_per_serving', ''),
            source_nutrition.get('total_fat_uom'),
            'G'
        )
        nutrition['total_fat_daily_percent'] = source_nutrition.get('dvp_total_fat', '')
        nutrition['total_sugars_g'] = self._check_unit_of_measure(
            source_nutrition.get('sugar_per_serving', ''),
            source_nutrition.get('sugar_uom'),
            'G'
        )
        nutrition['trans_fat_g'] = self._check_unit_of_measure(
            source_nutrition.get('trans_fat_per_serving', ''),
            source_nutrition.get('trans_fat_uom'),
            'G'
        )
        nutrition['vitamin_a_daily_percent'] = source_nutrition.get('dvp_vitamin_a', '')
        nutrition['vitamin_c_daily_percent'] = source_nutrition.get('dvp_vitamin_c', '')
        nutrition['vitamin_d_daily_percent'] = source_nutrition.get('dvp_vitamin_d', '')

        return nutrition

    def _check_unit_of_measure(self, value, source_unit, destination_unit):
        if value and source_unit != destination_unit:
            try:
                if isinstance(value, basestring):
                    value = float(value.replace(',', '.'))
                if source_unit == 'G' and destination_unit == 'MG':
                    value *= 1000
                elif source_unit == 'MG' and destination_unit == 'G':
                    value /= 1000
            except:
                self.logger.error('Can not convert {} from {} to {}: {}'.format(
                    value, source_unit, destination_unit, traceback.format_exc()))
        return value

    @staticmethod
    def _load_products(sheet):
        rows = sheet.get_rows()
        # header row 1
        header = [h.value.strip() for h in rows.next()]

        # skip description row 2
        rows.next()
        # skip requirements 3
        rows.next()

        for row in rows:
            yield dict(zip(header, map(lambda cell: cell.value, row)))


class PepsicoSamsParser(PepsicoParser):
    company = 'pepsico_standard'

    def __init__(self, *args, **kwargs):
        super(PepsicoSamsParser, self).__init__(*args, **kwargs)
        self.pepsico_images_filter = self._filter_images

    @staticmethod
    def _filter_images(image):
        if isinstance(image, dict):
            view = image.get('View')
            if view:
                return view not in ('1', '3')
        return True


class PepsicoTargetParser(PepsicoParser):
    company = 'pepsico_target'

    def __init__(self, *args, **kwargs):
        super(PepsicoTargetParser, self).__init__(*args, **kwargs)
        self.pepsico_images_filter = self._filter_images

    @staticmethod
    def _filter_images(image):
        if isinstance(image, dict):
            view = image.get('View')
            if view:
                return view not in ('1', '2', '3', '4', '5')
        return True
