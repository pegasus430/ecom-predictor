import unittest
import os
import sys

# set up paths
CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CWD)
sys.path.insert(1, os.path.join(CWD, '..'))

from validation import (BaseValidator, _get_fields_to_check,
                        _csv_file_to_data, _get_spider_output_filename)
from items import SiteProductItem


class ValidationTests(unittest.TestCase):

    def _dump_str_to_file(self, fname, content):
        with open(fname, 'wb') as fh:
            fh.write(content)

    def _setup_test_spider(self):
        spider = BaseValidator()
        spider.name = 'test'
        return spider

    def test_get_failed_fields(self):
        spider = self._setup_test_spider()
        fname = _get_spider_output_filename(spider)
        # all should fail
        data = """
brand`buyer_reviews`description`image_url`is_in_store_only`is_out_of_stock`\
locale`model`price\`ranking`related_products`results_per_page`title`\
total_matches`upc`url
```````````````
```````````````
        """
        self._dump_str_to_file(fname, data)
        self.assertEqual(
            spider._get_failed_fields(_csv_file_to_data(fname)).keys(),
            _get_fields_to_check(SiteProductItem)
        )
        # all should fail except upc
        data = """
brand`buyer_reviews`description`image_url`is_in_store_only`is_out_of_stock`\
locale`model`price`ranking`related_products`results_per_page`title`\
total_matches`upc`url
``````````````123456789012`
``````````````123456789013`
        """
        self._dump_str_to_file(fname, data)
        self.assertEqual(
            spider._get_failed_fields(_csv_file_to_data(fname)).keys(),
            sorted(
                [f for f in _get_fields_to_check(SiteProductItem)
                 if f != 'upc'],
                key=lambda v: v
            )
        )
        # all should fail except upc and description
        data = """
brand`buyer_reviews`description`image_url`is_in_store_only`is_out_of_stock`\
locale`model`price`ranking`related_products`results_per_page`title`\
total_matches`upc`url
``````````````123456789012`
``````````````123456789013`
        """
        self._dump_str_to_file(fname, data)
        spider.settings.ignore_fields = ['description']
        self.assertEqual(
            spider._get_failed_fields(_csv_file_to_data(fname)).keys(),
            sorted(
                [f for f in _get_fields_to_check(SiteProductItem)
                 if f not in ('upc', 'description')],
                key=lambda v: v
            )
        )
        # all should fail except upc and description and image_url
        data = """
brand`buyer_reviews`description`image_url`is_in_store_only`is_out_of_stock`\
locale`model`price`ranking`related_products`results_per_page`title`\
total_matches`upc`url
```http://blabla.com/i.jpg```````````123456789012`
```http://blabla2.com/i2.jpg```````````123456789013`
        """
        self._dump_str_to_file(fname, data)
        spider.settings.ignore_fields = ['description']
        self.assertEqual(
            spider._get_failed_fields(_csv_file_to_data(fname)).keys(),
            sorted(
                [f for f in _get_fields_to_check(SiteProductItem)
                 if f not in ('upc', 'description', 'image_url')],
                key=lambda v: v
            )
        )
        # all should fail except upc and description and image_url
        data = """
```http://blabla.com/i.jpg```````````123456789012`
```http://blabla2.com/i2.jpg```````````123456789013`
        """
        self._dump_str_to_file(fname, data)
        spider.settings.ignore_fields = ['description']
        self.assertEqual(
            spider._get_failed_fields(_csv_file_to_data(fname),
                                      exclude_first_line=False).keys(),
            sorted(
                [f for f in _get_fields_to_check(SiteProductItem)
                 if f not in ('upc', 'description', 'image_url')],
                key=lambda v: v
            )
        )

        # all should fail except upc and description and image_url
        data = """
brand`buyer_reviews`description`image_url`is_in_store_only`is_out_of_stock`\
locale`model`price`ranking`related_products`results_per_page`title`\
total_matches`upc`url
```http://blabla.com/i.jpg```````````123456789012`
apple```http://blabla2.com/i2.jpg```````````123456789013`
        """
        self._dump_str_to_file(fname, data)
        spider.settings.ignore_fields = ['description']
        spider.settings.optional_fields = ['brand']
        self.assertEqual(
            spider._get_failed_fields(_csv_file_to_data(fname)).keys(),
            sorted(
                [f for f in _get_fields_to_check(SiteProductItem)
                 if f not in ('upc', 'description', 'image_url', 'brand')],
                key=lambda v: v
            )
        )
        # all should fail except upc and description and image_url
        data = """
brand`buyer_reviews`description`image_url`is_in_store_only`is_out_of_stock`\
locale`model`price`ranking`related_products`results_per_page`title`\
total_matches`upc`url
apple```http://blabla.com/i.jpg```````````123456789012`
```http://blabla2.com/i2.jpg```````````123456789013`
        """
        self._dump_str_to_file(fname, data)
        spider.settings.ignore_fields = ['description']
        spider.settings.optional_fields = []
        self.assertEqual(
            sorted(spider._get_failed_fields(_csv_file_to_data(fname)).keys(),
                   key=lambda v: v),
            sorted(
                [f for f in _get_fields_to_check(SiteProductItem)
                 if f not in ('upc', 'description', 'image_url')],
                key=lambda v: v
            )
        )

    def test_check_ranking_consistency(self):
        spider = self._setup_test_spider()
        self.assertTrue(spider._check_ranking_consistency([1, 3, 2, 4]))
        self.assertFalse(spider._check_ranking_consistency((1, 2, 4)))


if __name__ == '__main__':
    unittest.main()