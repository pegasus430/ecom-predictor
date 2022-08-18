# TODO:
# * configurable auto-tests:
#    - various requests and their statuses (expected num of products; 'not found' products)
#    - web-frontend and alerts for auto-tests
#    - 'soft' alerts (sometimes something may fail but will be back to normal soon, so throw alerts only when some error is stable)

import os
import re
import json
from pprint import pprint
from collections import OrderedDict
import logging
import difflib
import datetime

from scrapy.log import INFO
from scrapy import signals
from scrapy.xlib.pydispatch import dispatcher
from scrapy.contrib.exporter import JsonLinesItemExporter
from twisted.python import log

from product_ranking.items import SiteProductItem


class bcolors:  # constants to avoid using any 3rd-party lib
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


def errors_to_html(errors):
    main_template = """<table>{rows_str}</table>"""
    row_template = """<tr><th align="left">%s</th>
<td class='value'>%s</td></tr>"""
    rows = []
    for error in errors.items():
        rows.append(row_template % (error[0], error[1]))
    rows_str = "".join(rows)
    main_template = main_template.format(rows_str=rows_str)
    return main_template


def _on_spider_close(spider, reason):

    # the next comments are here just to avoid forgetting the details
    #if reason.lower() == 'finished':  # all the website has been crawled
    #    pass
    #if reason.lower() == 'shutdown':  # closed by ctrl+c
    #    pass
    #print 'SPIDER', spider
    #print 'REASON', reason
    #print '#' * 79
    validation_errors = spider.errors()

    print bcolors.HEADER
    print 'Found', \
        len(_json_file_to_data(_get_spider_output_filename(spider))), \
        'products'
    print 'VALIDATION RESULTS:'
    print bcolors.ENDC
    if validation_errors:
        print bcolors.FAIL
        print 'ISSUES FOUND!'
        pprint(validation_errors.items())
        print bcolors.ENDC
    else:
        print bcolors.OKGREEN
        print 'NO ISSUES FOUND'
        print bcolors.ENDC


def _get_item_fields(cls):
    """ Returns the Item fields sorted by alphabet """
    fields = cls.fields.keys()
    return sorted(fields, key=lambda v: v)


def _get_fields_to_check(cls, single_mode=False):
    """ Returns all the Item fields except unnecessary ones
        which we don't want to check. """
    exclude = ['search_term', 'search_term_in_title_exactly',
               'search_term_in_title_interleaved',
               'search_term_in_title_partial', 'site']
    if single_mode:
        exclude += ['ranking', 'is_single_result', 'results_per_page',
                    'total_matches']

    fields = _get_item_fields(cls)
    return sorted(
        [f for f in fields if f not in exclude],
        key=lambda v: v
    )


def _json_file_to_data(fname):
    """ Returns JSON lines """
    data = []
    if not os.path.exists(fname):
        return []
    with open(fname, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            line = line.strip().replace('\n', '')
            data.append(json.loads(line))
    return data


def _extract_ranking(json_data):
    """ Extracts and returns unordered `ranking` values.
        The first row must be the table header.
        Returns an empty list if no data provided,
         None if there is any error, and the list of values otherwise.
    """
    if not json_data:
        return []  # no data provided
    column_index = None
    result_values = []
    for row in json_data:
        try:
            result_values.append(row.get('ranking', '1'))
        except:
            assert False, str(row) + '_______________' + str(column_index)
    result_values = [int(r) for r in result_values
                     if isinstance(r, int) or r.isdigit()]
    return result_values


def _get_spider_output_filename(spider):
    # not really cross-platform, but okay for *nix and Mac OS
    return '/tmp/%s_output.jl' % spider.name


def _get_spider_log_filename(spider):
    return '/tmp/%s_output.log' % spider.name


class ValidatorPipeline(object):
    """ Exports items in a temporary JSON file.
        Unnecessary fields are excluded. """

    def __init__(self):
        self.exporter = None
        self.files = {}

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        crawler.signals.connect(pipeline.spider_opened, signals.spider_opened)
        crawler.signals.connect(pipeline.spider_closed, signals.spider_closed)
        return pipeline

    def spider_opened(self, spider):
        fname = open(_get_spider_output_filename(spider), 'wb')
        self.files[spider] = fname
        self.exporter = JsonLinesItemExporter(fname)
        self.exporter.fields_to_export = _get_fields_to_check(SiteProductItem)
        self.exporter.start_exporting()

    def spider_closed(self, spider):
        self.exporter.finish_exporting()
        f = self.files.pop(spider)
        f.close()

    def process_item(self, item, spider):
        self.exporter.export_item(item)
        return item


class BaseValidatorSettings(object):

    # JSON output fields
    ignore_fields = []  # fields that shouldn't be validated at all
    optional_fields = []  # fields that should present at some\
                                     #  rows, but not in every row

    # spider log
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = False  # ... duplicated requests?
    ignore_log_filtered = False  # ... filtered requests?
    ignore_log_duplications_and_ranking_gaps = False  # ranking issues + dupls.

    # Test requests {request: [min_products; max_products], ...}
    # The requests below are for example purposes only!
    #  You have to override them! should be not less than 10 requests:
    #   not less than 2 'zero' requests, and not less than 8 'range' requests
    test_requests = {
        'abrakadabra': 0,  # should return 'no products' or just 0 products
        'nothing_found_123': 0,
        'iphone 9': [200, 800],  # should return from 200 to 800 products
        'a': [200, 800], 'b': [200, 800], 'c': [200, 800], 'd': [200, 800],
        'e': [200, 800], 'f': [200, 800], 'g': [200, 800],
    }


class BaseValidator(object):
    """ Validates the spider output.
        Don't forget to pass `-a validate=1` param while executing the spider.
    """

    settings = BaseValidatorSettings  # you may add () to instantiate class

    def __init__(self, *args, **kwargs):
        self.single_mode = kwargs.get('product_url', False)
        self.validate = kwargs.get('validate', False)
        if self.validate:
            log.msg('Validation is ON', level=INFO)
        else:
            log.msg('Validation is OFF', level=INFO)
        if self.validate:
            if not hasattr(self, 'settings'):
                assert False, 'you should define validation settings'
            # remove any possible old output\log files
            if os.path.exists(_get_spider_output_filename(self)):
                os.unlink(_get_spider_output_filename(self))
            if os.path.exists(_get_spider_log_filename(self)):
                os.unlink(_get_spider_log_filename(self))
            # setup logging
            logging.basicConfig(level=logging.INFO, filemode='w',
                                filename=_get_spider_log_filename(self))
            observer = log.PythonLoggingObserver()
            observer.start()
            # check validation settings
            _test_requests_zero_count = 0
            _test_requests_range_count = 0
            _test_requests_with_spaces = 0
            for req_key, req_val in self.settings.test_requests.items():
                if req_val == 0:
                    _test_requests_zero_count += 1
                else:
                    _test_requests_range_count += 1
                if ' ' in req_key:
                    _test_requests_with_spaces += 1
            # if _test_requests_zero_count < 2:
            #     assert False, ('.settings.test_requests should have '
            #                    'at least 2 `zero` requests')
            # if _test_requests_range_count < 8:
            #     assert False, ('.settings.test_requests should have '
            #                    'at least 8 `range` requests')
            # if _test_requests_with_spaces == 0:
            #     assert False, ('.settings.test_requests should have '
            #                    'at least 1 request with space')
            # connect on_close signal
            dispatcher.connect(_on_spider_close, signals.spider_closed)
            self.exporter = None  # we're going to use our own exporter
            self._check_validators()
            # check if the same field(s) has(have) been added
            #  to the both lists
            shared_fields = (set(self.settings.ignore_fields)
                             & set(self.settings.optional_fields))
            assert not shared_fields, \
                ('these field(s) exist(s) in both'
                 ' validation lists: ' + str(shared_fields))
        super(BaseValidator, self).__init__(*args, **kwargs)

    def _check_validators(self):
        """ Checks that our own validator methods are ok """
        fields = _get_fields_to_check(SiteProductItem, self.single_mode)
        for field in fields:
            if not hasattr(self, '_validate_'+field):
                assert False, ('validation method for field ' + field
                               + ' does not exist')
            if not callable(getattr(self, '_validate_'+field)):
                assert False, ('validation method for field ' + field
                               + ' is not callable')

    def _validate_brand(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 35:  # too long
            return False
        if val.strip().count(u' ') > 5:  # too many spaces
            return False
        if '<' in val or '>' in val:  # no tags
            return False
        return True

    def _validate_description(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 10000:  # too long
            return False
        return True

    def _validate_image_url(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 500:  # too long
            return False
        if val.strip().count(u' ') > 5:  # too many spaces
            return False
        if not val.strip().lower().startswith('http'):
            return False
        return True

    def _validate_categories_full_info(self, val):
        if val in ('', None):
            return True
        if not isinstance(val, list):
            return False
        for _v in val:
            if 'name' not in _v or 'url' not in _v:
                return False
        return True

    def _validate_is_in_store_only(self, val):
        return val in ('True', 'False')

    def _validate_is_out_of_stock(self, val):
        return val in ('True', 'False')

    def _validate_locale(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 10:  # too long
            return False
        if val.strip().count(u' ') > 5:  # too many spaces
            return False
        if '<' in val or '>' in val:  # no tags
            return False
        return True

    def _validate_model(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 50:  # too long
            return False
        if val.strip().count(u' ') > 7:  # too many spaces
            return False
        if '<' in val or '>' in val:  # no tags
            return False
        return True

    def _validate_price(self, val):
        if val is None:
            return True
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 50:  # too long
            return False
        if '<' in val or '>' in val:  # no tags
            return False
        if not re.match(r'Price\(priceCurrency=\w{2,3}, price=[\d.]{1,15}\)$', val):
            return False
        return True

    def _validate_special_pricing(self, val):
        return val in (True, False, None)

    def _validate_ranking(self, val):
        if isinstance(val, int):
            return True
        if not val.strip().isdigit():
            return False
        return True

    def _validate_related_products(self, val):
        if not bool(str(val).strip()):  # empty
            return False
        if not str(val).strip().startswith('{'):
            return False
        if val:
            if isinstance(val, (str, unicode)):
                val = json.loads(val)
            if val:
                _v, _k = val.items()[0]
                if not isinstance(_v, (str, unicode)):
                    return False
                if not isinstance(_k, list):
                    return False
        return True

    def _validate_results_per_page(self, val):
        val = str(val)
        if not bool(val.strip()):  # empty
            return False
        if not val.strip().isdigit():
            return False
        val = int(val.strip())
        return 0 < val < 200

    def _validate_title(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 300:  # too long
            return False
        if val.strip().count(u' ') > 50:  # too many spaces
            return False
        if '<' in val and '>' in val:  # no tags
            return False
        return True

    def _validate_total_matches(self, val):
        val = str(val)
        if not bool(val.strip()):  # empty
            return False
        if not val.strip().isdigit():
            return False
        val = int(val.strip())
        return 0 <= val < 99999999

    def _validate_upc(self, val):
        return re.match(r'^\d{12}$', val.strip())

    def _validate_url(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 500:  # too long
            return False
        if val.strip().count(u' ') > 5:  # too many spaces
            return False
        if not val.strip().lower().startswith('http'):
            return False
        return True

    def _validate_buyer_reviews(self, val):
        if val in (0, True, False, ''):
            return True
        if isinstance(val, basestring):
            try:
                val = json.loads(val)
            except:
                return False
        if isinstance(val, dict):
            val = val['buyer_reviews']
        if isinstance(val, basestring):
            val = json.loads(val)
        if not val:
            return True  # empty object?
        if not isinstance(val, (list, tuple)):
            return False
        if len(val) != 3:
            return False
        if not isinstance(val[0], (int, float)):
            return False
        if not isinstance(val[1], (int, float)):
            return False
        if not val[2]:
            return False
        marks = sorted([int(m) for m in val[2].keys()])
        if marks != range(1, 6):
            return False
        for mark_key, mark_value in val[2].items():
            if int(mark_value) < 0 or int(mark_value) > 99999999:
                return False
        return True

    def _validate_google_source_site(self, val):
        if not isinstance(val, basestring) and not val:
            return False

        try:
            val = json.loads(val)
        except:
            return False

        if not isinstance(val, dict):
            return False

        for v in val:
            if 'currency' not in v:
                return False
            if 'price' not in v:
                return False

        return True

    # Added.
    def _validate_is_mobile_agent(self, val):
        if val in ('', None):
            return True
        return val in ('True', 'False')

    # Added.
    def _validate_is_single_result(self, val):
        if val in ('', None):
            return True
        return val in ('True', 'False')

    # Added.
    def _validate_scraped_results_per_page(self, val):
        if val in ('', None):
            return True
        if isinstance(val, int):
            return True
        return False

    # Added.
    def _validate_sponsored_links(self, val):
        if val in ('', None):
            return True

        if isinstance(val, basestring):
            try:
                val = json.loads(val)
            except:
                return False

        if isinstance(val, (tuple, list)):
            for v in val:
                if not isinstance(v, dict):
                    return False
        return True

    def _validate_category(self, val):
        if val in (None, ''):
            return True
        if isinstance(val, basestring):
            try:
                val = json.loads(val)
            except Exception as e:
                return False
        if isinstance(val, (tuple, list)):
            return True
        return False

    def _validate_categories(self, val):
        if not val:
            return True
        for v in val:
            if not isinstance(v, (str, unicode)):
                return False
        return True

    def _validate_seller_ranking(self, val):
        if not val:
            return True
        if isinstance(val, basestring):
            try:
                val = json.loads(val)
            except Exception as e:
                return False
        if isinstance(val, (tuple, list)):
            return True


    def _validate_bestseller_rank(self, val):
        if isinstance(val, int):
            return True
        if not val.isdigit():
            return False
        return True

    def _validate_date_of_last_question(self, val):
        if val in ('', None):
            return True
        try:
            date = datetime.datetime.strptime(val, '%Y-%m-%d')
        except:
            try:
                date = datetime.datetime.strptime(val, '%d-%m-%Y')
            except:
                return False
        return True

    def _validate_department(self, val):
        val = unicode(val)
        if len(val) > 100:
            return False
        return True

    def _validate_is_pickup_only(self, val):
        return val in (True, False, None, '')

    def _validate_limited_stock(self, val):
        if isinstance(val, list):
            return val[0] in (True, False, None, '')
        return val in (True, False, None, '')

    def _validate_marketplace(self, val):
        if val == '':
            return True
        if isinstance(val, basestring):
            try:
                val = json.loads(val)
            except:
                return False
        for v in val:
            if 'currency' not in v:
                return False
            if 'price' not in v:
                return False
            if 'name' not in v:
                return False
        return True

    def _validate_prime(self, val):
        if isinstance(val, basestring):
            if 'Prime' in val:
                return 4 < len(val) < 20
        return val in (True, False, None, '')

    def _validate_recent_questions(self, val):
        if val == '':
            return True
        if isinstance(val, basestring):
            try:
                val = json.loads(val)
            except:
                return False
        for v in val:
            if not any(['date' in k.lower() for k in v.keys()]):
                return False
        return True

    def _validate_shipping(self, val):
        return val in (True, False, None, '')

    def _validate_variants(self, val):
        if val and isinstance(val, basestring):
            try:
                val = json.loads(val)
            except:
                return False
        if val and not isinstance(val, (list, tuple)):
            return False
        return True

    def _validate_shelf_page_out_of_stock(self, val):
        return val in ('', 0, 1)

    def _validate__walmart_redirected(self, val):
        return True  # we will not validate this field for now

    def _validate__walmart_original_id(self, val):
        return True  # we will not validate this field for now

    def _validate__walmart_current_id(self, val):
        return True  # we will not validate this field for now

    def _validate__walmart_original_price(self, val):
        return True  # we will not validate this field for now

    def _validate__walmart_original_oos(self, val):
        return True  # we will not validate this field for now

    def _validate_last_buyer_review_date(self, val):
        if not val:
            return True
        try:
            _ = datetime.datetime.strptime(val, "%d-%m-%Y")
        except Exception, e:
            return False
        return True

    def _validate_price_subscribe_save(self, val):
        if not val:
            return True
        if re.match(r'^[\d\.]+$', str(val)):
            return True

    def _validate_price_original(self, val):
        if not val:
            return True
        if re.match(r'^[\d\.]+$', str(val)):
            return True

    def _validate_response_code(self, val):
        if not val:
            return True
        if val.isdigit():
            if 0 < val < 999:
                return True

    def _validate_assortment_url(self, val):
        return True

    def _validate_deliver_in(self, val):
        return True  # TODO: update

    def _validate__statistics(self, val):
        return True

    def _validate_sku(self, val):
        return True  # TODO: update

    def _validate_no_longer_available(self, val):
        return val in (True, False, None, '')

    def _validate_not_found(self, val):
        return val in (True, False, None, '')

    def _validate_shelf_name(self, val):
        return True  # TODO: update

    def _validate_shelf_path(self, val):
        return True  # TODO: update

    def _validate_img_count(self, val):
        return val in (None, '') or val in range(0, 999)

    def _validate_video_count(self, val):
        return val in (None, '') or val in range(0, 999)

    def _validate_price_details_in_cart(self, val):
        return val in (None, '', True, False)

    def _validate_all_questions(self, val):
        if val in (None, '', []):
            return True
        for _d in val:
            if not isinstance(_d, dict):
                return False
        return True

    def _validate__subitem(self, val):
        return val in (True, False, None, '')

    def _validate__jcpenney_has_size_range(self, val):
        return val in (True, False, None, '')

    def _validate_level1(self, val):
        return val in (True, False, None, '')

    def _validate_level2(self, val):
        return val in (True, False, None, '')

    def _validate_level3(self, val):
        return val in (True, False, None, '')

    def _validate_level4(self, val):
        return val in (True, False, None, '')

    def _validate_level5(self, val):
        return val in (True, False, None, '')

    def _validate_level6(self, val):
        return val in (True, False, None, '')

    def _validate_level7(self, val):
        return val in (True, False, None, '')

    def _validate_level8(self, val):
        return val in (True, False, None, '')

    def _validate_level9(self, val):
        return val in (True, False, None, '')

    def _validate_level10(self, val):
        return val in (True, False, None, '')

    def _validate_dpci(self, val):
        return val in (True, False, None, '')

    def _validate_tcin(self, val):
        return val in (True, False, None, '')

    def _validate_origin(self, val):
        return val in (True, False, None, '')

    def _validate_asin(self, val):
        return True  # TODO: better validation!

    def _validate_available_online(self, val):
        return True  # TODO: better validation!

    def _validate_available_store(self, val):
        return True  # TODO: better validation!

    def _validate_is_sponsored_product(self, val):
        return True  # TODO: better validation!

    def _validate_minimum_order_quantity(self, val):
        return True  # TODO: better validation!

    def _validate_price_club(self, val):
        return True  # TODO: better validation!

    def _validate_price_club_with_discount(self, val):
        return True  # TODO: better validation!

    def _validate_price_with_discount(self, val):
        return True  # TODO: better validation!

    def _validate_shipping_cost(self, val):
        return True  # TODO: better validation!

    def _validate_shipping_included(self, val):
        return True  # TODO: better validation!

    def _validate_subscribe_and_save(self, val):
        return True  # TODO: better validation!

    def _validate_walmart_category(self, val):
        return True  # TODO: better validation!

    def _validate_walmart_exists(self, val):
        return True  # TODO: better validation!

    def _validate_walmart_url(self, val):
        return True  # TODO: better validation!

    def _validate_target_category(self, val):
        return True  # TODO: better validation!

    def _validate_target_exists(self, val):
        return True  # TODO: better validation!

    def _validate_target_url(self, val):
        return True  # TODO: better validation!

    def _validate_item_not_available(self, val):
        return True  # TODO: better validation!

    def _validate_low_stock(self, val):
        return True  # TODO: better validation!

    def _validate_reseller_id(self, val):
        return True  # TODO: better validation!

    def _validate_search_redirected_to_product(self, val):
        return True  # TODO: better validation!

    def _validate_temporary_unavailable(self, val):
        return True  # TODO: better validation!

    def _get_failed_fields(self, data, add_row_index=False):
        """ Returns the fields with errors (and their first wrong values)
        :param data: 2-dimensions list or str
        :param exclude_first_line: bool
        :param add_row_index: bool (will add Row index to every wrong value)
        :return: dict that contains dict with fields {field_name: first_wrong_value,...} or None
        """
        failed_fields = []
        # validate each field in the row
        optional_ok_fields = []  # put fields there if at least 1 is ok

        for row_i, row in enumerate(data):
            for _, field_name in enumerate(
                    _get_fields_to_check(SiteProductItem, self.single_mode)):
                if field_name in self.settings.ignore_fields:
                    continue
                # `optional` marker
                is_optional = False
                if field_name in self.settings.optional_fields:
                    is_optional = True
                field_validator = getattr(self, '_validate_'+field_name, None)
                try:
                    _value = row[field_name]
                except (IndexError, KeyError):
                    _value = ''  # empty string if no such value at all
                if isinstance(_value, str):
                    _value = _value.decode('utf8')  # avoid UnicodeDecodeError
                if not field_validator(_value):
                    failed_fields.append(
                        [is_optional, row_i, field_name, _value]
                    )
                else:
                    if is_optional and not field_name in optional_ok_fields:
                        optional_ok_fields.append(field_name)

        # validate optional fields (and remove those which are in fact ok)
        for i, (is_optional, row_i, field_name, field_value) in enumerate(
                failed_fields):
            if field_name in optional_ok_fields and is_optional:
                failed_fields[i] = None

        failed_fields = [f for f in failed_fields if f is not None]

        failed_fields_with_values = OrderedDict()
        for is_optional, row_i, field_name, field_value in failed_fields:
            if isinstance(field_value, unicode):
                field_value = field_value.encode('utf-8')
            if row_i not in failed_fields_with_values.keys():
                failed_fields_with_values[row_i] = {field_name: field_value}
            else:
                failed_fields_with_values[row_i][field_name] = field_value
            if not isinstance(failed_fields_with_values[row_i][field_name], str):
                failed_fields_with_values[row_i][field_name] \
                    = str(failed_fields_with_values[row_i][field_name])

        # save order
        failed_fields_with_values = OrderedDict(
            sorted(failed_fields_with_values.iteritems(), key=lambda v: v)
        )

        return (None if not failed_fields_with_values
                else failed_fields_with_values)

    def _check_ranking_consistency(self, ranking_values):
        """ Check that the given ranking list is correct.
            [1,2,3,4] - correct; [1,2,4] - incorrect.
            Allow about 5% of products to be missed (duplicated results in SERP?).
        :return: True if correct, False otherwise
        """
        if not isinstance(ranking_values, list):
            ranking_values = [r for r in ranking_values]
        ranking_values = sorted(ranking_values, key=lambda v: v)
        ratio = difflib.SequenceMatcher(None, ranking_values, range(1, len(ranking_values)+1)).ratio()
        return ratio >= 0.95

    def _check_logs(self):
        """ Returns issues found in the log (if any).
        :return: list of found issues
        """
        result = []
        fname = _get_spider_log_filename(self)
        with open(fname, 'r') as fh:
            content = fh.read()
        log_errors = ['log_count/ERROR', 'exceptions.', 'ERROR:twisted:']
        if any(err in content for err in log_errors):
            if 'No search terms provided!' in content and self.single_mode:
                pass
            else:
                result.append('ERRORS')
        if 'dupefilter/filtered' in content:
            result.append('DUPLICATIONS')
        if 'offsite/filtered' in content:
            result.append('FILTERED')
        return result

    def _validation_data(self):
        """ Just a useful wrapper """
        return _json_file_to_data(_get_spider_output_filename(self))

    def _validation_filename(self):
        """ Just a useful wrapper """
        return _get_spider_output_filename(self)

    def _validation_log_filename(self):
        """ Just a useful wrapper """
        return _get_spider_log_filename(self)

    def errors(self):
        """ Validates the whole item. Returns the list of failed fields or
            None if everything is ok. """
        found_issues = OrderedDict()

        fname = _get_spider_output_filename(self)
        data = _json_file_to_data(fname)

        # check wrong values (validates every row separately)
        failed_fields = self._get_failed_fields(data, add_row_index=True)

        if failed_fields:
            found_issues.update(failed_fields)

        if ('ranking' not in self.settings.optional_fields
                and 'ranking' not in self.settings.ignore_fields):
            # validate ranking (to make sure no products are missing)
            ranking_values = _extract_ranking(data)

            if ranking_values is None:
                found_issues.update(OrderedDict(ranking='field not found'))
            if not self._check_ranking_consistency(ranking_values):
                found_issues.update(
                    OrderedDict(ranking='some products missing'))

        log_issues = self._check_logs()

        if not self.settings.ignore_log_errors:
            if 'ERRORS' in log_issues:
                found_issues.update(OrderedDict(log_issues='errors found'))

        if not self.settings.ignore_log_duplications:
            if 'DUPLICATIONS' in log_issues:
                found_issues.update(
                    OrderedDict(log_issues='duplicated requests found'))

        if getattr(self.settings, 'ignore_log_duplications_and_ranking_gaps', None):
            # remove notifications about missing products and duplications
            found_issues.pop('ranking', None)
            found_issues.pop('log_issues', None)

        if not self.settings.ignore_log_filtered:
            if 'FILTERED' in log_issues:
                found_issues.update(
                    OrderedDict(log_issues='offsite filtered requests found'))

        return found_issues if found_issues else None

    def errors_html(self):
        errors = self.errors()
        if not errors:
            errors = {}
        return errors_to_html(errors)
