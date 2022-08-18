import re
import urllib
import urlparse
import json
import requests
import shutil
import mechanize
import cookielib
import os
import random
import os.path
import tempfile
import datetime
import csv
import logging
import xmltodict
import unirest
import time
import traceback

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from xlsxwriter.workbook import Workbook
from collections import OrderedDict
from django.views.generic import View as DjangoView
from django.core.context_processors import csrf
from django.shortcuts import render_to_response
from django.conf import settings
from django.core.servers.basehttp import FileWrapper
from django.db import connection
from django.template import loader
from rest_framework.response import Response
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from rest_framework.parsers import MultiPartParser, FormParser
from subprocess import Popen, PIPE, STDOUT
from lxml import html
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from rest_framework import viewsets, permissions
from walmart_api.serializers import (
    WalmartApiFeedRequestSerializer,
    WalmartApiItemsWithXmlFileRequestSerializer,
    WalmartApiItemsWithXmlTextRequestSerializer,
    WalmartApiValidateXmlTextRequestSerializer,
    WalmartApiValidateXmlFileRequestSerializer,
    WalmartDetectDuplicateContentRequestSerializer,
    WalmartDetectDuplicateContentFromCsvFileRequestSerializer,
    CheckItemStatusByProductIDSerializer,
    ToolIDSerializer,
    ListItemsWithErrorSerializer,
    RichMediaSerializer,
    FeedDetailsSerializer,
)
from walmart_api.models import SubmissionHistory, SubmissionXMLFile, SubmissionResults, RichMediaMarketingContent
from walmart_api.utils import RestFrameworkViewSetRendererTemplateNameMixin
from statistics.models import process_check_feed_response, sync_xml_item_statuses, ItemMetadata
from rest_apis_content_analytics.image_duplication.views import parse_data
from lxml import etree


logger = logging.getLogger('default')

unirest.timeout(30)


FREE_PROXY_IP_PORT_LIST = [
    "52.91.67.73",
    "52.90.231.48",
    "52.91.35.248",
    "52.90.102.54",
    "54.164.142.70",
    "52.90.206.144",
    "54.175.31.207",
    "52.91.180.193",
    "54.172.22.183",
    "52.90.182.115"
]

BROWSER_AGENT_STRING_LIST = {
    "Firefox": [
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1",
        "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10; rv:33.0) Gecko/20100101 Firefox/33.0"
    ],
    "Chrome": [
        "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36",
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1)"
            " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.1 Safari/537.36"
        ),
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36"
    ],
    "Safari": [
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3)"
            " AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A"
        ),
        (
            "Mozilla/5.0 (iPad; CPU OS 6_0 like Mac OS X)"
            " AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10A5355d Safari/8536.25"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8)"
            " AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2"
        )
    ]
}


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def choose_free_proxy_from_candidates():
    driver = webdriver.PhantomJS()
    driver.set_window_size(1440, 900)

    driver.get("https://proxy-list.org/english/index.php")

    select_country = driver.find_element_by_xpath("//form[@id='form-search']//select[@name='country']")
    select_country.click()
    option_usa_and_canada = driver.find_element_by_xpath(
        "//form[@id='form-search']//select[@name='country']/option[@value='usa-and-canada']"
    )
    option_usa_and_canada.click()

    select_type = driver.find_element_by_xpath("//form[@id='form-search']//select[@name='type']")
    select_type.click()
    option_anonymous_and_elite = driver.find_element_by_xpath(
        "//form[@id='form-search']//select[@name='type']/option[@value='anonymous-and-elite']"
    )
    option_anonymous_and_elite.click()

    submit_button = driver.find_element_by_xpath("//form[@id='form-search']//input[@value='Search proxy servers']")
    submit_button.click()

    page_raw_text = driver.page_source
    html_tree = html.fromstring(page_raw_text)

    '''
    select_list_length = driver.find_element_by_xpath("//select[@name='proxylisttable_length']")
    select_list_length.click()
    option_length_80 = driver.find_element_by_xpath("//select[@name='proxylisttable_length']/option[@value='80']")
    option_length_80.click()
    select_elite_proxy = driver.find_elements_by_xpath("//tfoot/tr//select")[3]
    select_elite_proxy.click()
    option_elite_proxy = driver.find_element_by_xpath("//tfoot/tr//select/option[@value='elite proxy']")
    option_elite_proxy.click()
    '''

    proxy_info_list = html_tree.xpath("//div[@id='proxy-table']//li[@class='proxy']/text()")[1:]
    driver.close()
    driver.quit()

    return {"http": random.choice(proxy_info_list)}


def remove_duplication_keeping_order_in_list(seq):
    if seq:
        seen = set()
        seen_add = seen.add
        return [x for x in seq if not (x in seen or seen_add(x))]

    return None


def select_browser_agents_randomly(agent_type=None):
    if agent_type and agent_type in BROWSER_AGENT_STRING_LIST:
        return random.choice(BROWSER_AGENT_STRING_LIST[agent_type])

    return random.choice(random.choice(BROWSER_AGENT_STRING_LIST.values()))


def initialize_browser_settings(browser):
    # Cookie Jar
    cj = cookielib.LWPCookieJar()
    browser.set_cookiejar(cj)

    # Browser options
    browser.set_handle_equiv(True)
    browser.set_handle_gzip(True)
    browser.set_handle_redirect(True)
    browser.set_handle_referer(True)
    browser.set_handle_robots(False)

    # Follows refresh 0 but not hangs on refresh > 0
    browser.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

    # Want debugging messages?
    # br.set_debug_http(True)
    # br.set_debug_redirects(True)
    # br.set_debug_responses(True)

    # User-Agent (this is cheating, ok?)
    browser.addheaders = [('User-agent', select_browser_agents_randomly())]

    return browser


def group_params(data, files, patterns):
    """ data = request.data, files=request.files,
        patterns = [param1_to_group, param2_to_group, etc.]
    """
    output = {}
    for data_item_name in data.keys():
        # there may be multiple files/fields being uploaded/sent at the same time
        for data_item_value in data.getlist(data_item_name):
            for pattern in patterns:
                if pattern in data_item_name:
                    param_reminder = data_item_name.replace(pattern, '').strip()
                    if not param_reminder:
                        param_reminder = 'default'
                    if param_reminder not in output:
                        output[param_reminder] = []
                    _item = {
                        'name': data_item_name,
                        'value': data_item_value,
                        'type': 'data',
                        'cleaned_name': data_item_name.replace(param_reminder, '')
                    }
                    if _item not in output[param_reminder]:
                        output[param_reminder].append(_item)
    for data_item_name in files.keys():
        for data_item_value in files.getlist(data_item_name):
            for pattern in patterns:
                if pattern in data_item_name:
                    param_reminder = data_item_name.replace(pattern, '').strip()
                    if not param_reminder:
                        param_reminder = 'default'
                    if param_reminder not in output:
                        output[param_reminder] = []
                    _item = {
                        'name': data_item_name, 'value': data_item_value, 'type': 'file',
                        'cleaned_name': data_item_name.replace(param_reminder, '')
                    }
                    if _item not in output[param_reminder]:
                        output[param_reminder].append(_item)
    return output


def find_in_list(lst, key_name, search_in_values=True):
    """ Returns the element of the list which has the given key_name in it """
    result = []
    for e in lst:
        if key_name in e:
            if e['value'] not in result:
                result.append(e['value'])
        if search_in_values:
            for _key, _value in e.items():
                if _value == key_name:
                    if e['value'] not in result:
                        result.append(e['value'])
    return result


def merge_xml_files_into_one(*files):
    """ See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=6198 """
    output_file_template = """
<SupplierProductFeed xmlns="http://walmart.com/suppliers/">
    <version>1.4.1</version>
%s
</SupplierProductFeed>
"""
    output_file = tempfile.NamedTemporaryFile('wb', suffix='.xml', delete=False)
    _sub_templates = ""
    for f in files:
        file_cont = f.read()
        pos1 = file_cont.find('<SupplierProduct>')
        pos2 = file_cont.rfind('</SupplierProduct>') + len('</SupplierProduct>')
        if pos1 == -1 or pos2 == -1:
            print('Invalid XML file content - could not find "SupplierProduct" opening or closing tag')
            continue
        _sub_templates += ' '*4 + file_cont[pos1:pos2].strip() + '\n'
    output_file.seek(0)
    output_file.write((output_file_template % _sub_templates.strip('\n')).strip())
    output_file.close()
    return output_file.name


class ErrorResponse(object):
    """ A custom error notification """
    def __init__(self, error_type, msg):
        self.error_type = str(error_type)
        self.msg = msg

    def to_json(self):
        return {'error_type': self.error_type, 'error_message': self.msg}

    def to_html(self):
        raise NotImplementedError

    def to_response(self):
        return Response(self.to_json())


def get_walmart_api_invoke_log(request_or_user, base_file=__file__):
    if hasattr(request_or_user, 'user'):
        request_or_user = request_or_user.user
    if not request_or_user.is_authenticated():
        return
    return (
        os.path.dirname(os.path.realpath(base_file)) +
        '/user-' +
        str(request_or_user.pk) +
        '__' +
        'walmart_api_invoke_log.txt'
    )


def parse_walmart_api_log(request_or_user, base_file=__file__):
    from dateutil.parser import parse as parse_date

    def _parse_date(_date):
        try:
            return datetime.datetime.strptime(_date.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            return parse_date(_date.strip())

    log = get_walmart_api_invoke_log(request_or_user, base_file)
    if os.path.isfile(log):
        with open(log, 'r') as fh:
            for line in fh:
                line = line.strip()
                if ',' not in line:
                    continue
                if len(line.split(',')) == 3:
                    date, upc, feed_id = line.split(',')
                    yield {
                        'datetime': _parse_date(date.strip()),
                        'upc': upc.strip(),
                        'feed_id': feed_id
                    }
                else:
                    date, upc, server_name, client_ip, feed_id = line.split(',')
                    yield {
                        'datetime': _parse_date(date.strip()),
                        'upc': upc.strip(),
                        'feed_id': feed_id,
                        'server_name': server_name,
                        'client_ip': client_ip
                    }


def validate_walmart_product_xml_against_xsd(product_xml_string):
    current_path = os.path.dirname(os.path.realpath(__file__))
    xmlschema_doc = etree.parse(current_path + "/walmart_suppliers_product_xsd/SupplierProductFeed.xsd")
    xmlschema = etree.XMLSchema(xmlschema_doc)
    xmlparser = etree.XMLParser(schema=xmlschema)
    product_xml_string = product_xml_string.strip()

    if product_xml_string.startswith("<?xml"):
        product_xml_string = product_xml_string[product_xml_string.find("<", 2):]

    proudct_xml_list = re.findall('<SupplierProduct>(.*?)</SupplierProduct>', product_xml_string, re.DOTALL)
    product_xml_version = re.findall('<version>(.*?)</version>', product_xml_string, re.DOTALL)
    if not product_xml_version:
        return 'error - no product xml version found'
    product_xml_version = product_xml_version[0]
    validation_results = OrderedDict()

    for index, product_xml in enumerate(proudct_xml_list):
        try:
            product_xml = "<SupplierProductFeed xmlns='http://walmart.com/suppliers/'>" \
                          "<version>{0}</version>" \
                          "<SupplierProduct>{1}</SupplierProduct>" \
                          "</SupplierProductFeed>".format(product_xml_version, product_xml.strip())
            product_xml.decode("utf-8").encode("utf-8")
            etree.fromstring(product_xml, xmlparser)
            validation_results['product index ' + str(index + 1)] = 'success - this product is validated by Walmart product xsd files.'
        except Exception, e:
            print e
            validation_results['product index ' + str(index + 1)] = 'error - ' + str(e)

    return validation_results


# Create your views here.


class InvokeWalmartApiViewSet(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = WalmartApiItemsWithXmlFileRequestSerializer
    parser_classes = (FormParser, MultiPartParser,)

    """
    Walmart API credential info
    """

    walmart_consumer_id = "a8bab1e0-c18c-4be7-b47a-0411153b7514"
    walmart_private_key = "MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBALBpb58mZiP4VHwx6R7fbPd/u7T22eE7vxECjsS6QHulIN/DExLSFIUrKzHgM11hm7ElRh35cKLcBR/XXZw6u/FTzFQbCiRmuDnJyz53PZi/YjhGTD2GY7jIqVILBz30J/3HRnPx9V0nBnWEEeKBeqb3rYJqsr8k1r71Sy45xey9AgMBAAECgYBFDA+PWCU0QPc4YQSge8yXlpwueUvQF2VyT/D3WPryKjCSxDSL8kPr13ihneIc055vmGo4QzBt3fX3f4D5LBfw9YFH0u29At2p9AH4FiyejhEeQ2tWNR4+zOUiMFVxDyM03zlKAsoJcRz1USklr0J1NtRnPBY7RslXU+wnps4RVQJBAPgzIV5Uo8uT4WYrbxc+Yu4Yd8imFqvGuhZpZdeS1EsRObseZc++v360k5Dx/rJzzJqd4JmeQjMJ2Y76V62jcQsCQQC19L4WYn0EYrPuGWMMoswKmOGHlU8eg3JVooZ/ufrvb6YNjVTDHMFLhU5Netw1s2eMo927giLQXF5+7ANg5MZXAkAqBrZau6g0e2jKHQalf+nOeRQnRIBIO9EcpGIbO4B46YTF+2Kv55OTR85I18ERxGvbrmnueQ6qh7tv61HXU/p7AkAqxePBg1l8JG/DsvgTyllIzHOH2dOFisTf2Jrhf6i7jHVujiC01RejVyz3DcCiZxAagZLoN0lTzcLw9y48Ist1AkEA28Opbyzq6BZOZMvXAQ/HEOGW4CVZZ9rHOwp6JByAIHxQcvwQ++TU/118qdA1HriZTZxGE1dZwnDEa2I79ICfrg=="
    walmart_svc_name = "Walmart Marketplace"
    walmart_environment = "Walmart Marketplace"
    walmart_version = "2nd"
    walmart_qos_correlation_id = "123456abcdef"

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    @staticmethod
    def generate_walmart_api_signature(walmart_api_end_point, consumer_id, private_key, request_method, file_path):
        cmd = 'java -jar "'
        cmd += os.path.dirname(os.path.realpath(__file__))
        cmd += '/DigitalSignatureUtil-1.0.0.jar" '
        cmd += '{0} {1} {2} {3} {4}'
        cmd = cmd.format(walmart_api_end_point, consumer_id, private_key, request_method, file_path)

        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.readlines()

        if not output[0].startswith("WM_SEC.AUTH_SIGNATURE:") or not output[1].startswith("WM_SEC.TIMESTAMP:"):
            return None

        walmart_api_signature = {
            "signature": output[0][len("WM_SEC.AUTH_SIGNATURE:"):-1],
            "timestamp": output[1][len("WM_SEC.TIMESTAMP:"):-1]
        }
        return walmart_api_signature

    def create(self, request):
        try:
            request_data = request.data
            request_files = request.FILES
            walmart_api_signature = self.generate_walmart_api_signature(
                request_data["request_url"],
                self.walmart_consumer_id,
                self.walmart_private_key,
                request_data["request_method"].upper(),
                "signature.txt"
            )

            if not walmart_api_signature:
                print "Failed in generating walmart api signature."
                return Response({'data': "Failed in generating walmart api signature."})

            with open(os.path.dirname(os.path.realpath(__file__)) + "/upload_file.xml", "wb") as upload_file:
                xml_data_by_list = request_files["xml_file_to_upload"].read()
                xml_data_by_list = xml_data_by_list.splitlines()

                for xml_row in xml_data_by_list:
                    upload_file.write((xml_row + "\n").encode("utf-8"))

            upload_file = open(os.path.dirname(os.path.realpath(__file__)) + "/upload_file.xml", "rb")

            response = unirest.post(
                request_data["request_url"],
                headers={
                    "Accept": "application/json",
                    "WM_CONSUMER.ID": self.walmart_consumer_id,
                    "WM_SVC.NAME": self.walmart_svc_name,
                    "WM_QOS.CORRELATION_ID": self.walmart_qos_correlation_id,
                    "WM_SVC.VERSION": self.walmart_version,
                    "WM_SVC.ENV": self.walmart_environment,
                    "WM_SEC.AUTH_SIGNATURE": walmart_api_signature["signature"],
                    "WM_SEC.TIMESTAMP": int(walmart_api_signature["timestamp"])
                },
                params={"file": upload_file, }
            )

            if type(response.body) is dict:
                # return Response(response.body)

                '''''''''''''''''''''''''''''''''''
                Check feed status begin
                '''''''''''''''''''''''''''''''''''
                walmart_api_signature = self.generate_walmart_api_signature(
                    'https://marketplace.walmartapis.com/v2/feeds/{0}?includeDetails=true'.format(response.body['feedId']),
                    self.walmart_consumer_id,
                    self.walmart_private_key,
                    "GET",
                    "signature.txt"
                )

                response = unirest.get(
                    'https://marketplace.walmartapis.com/v2/feeds/{0}?includeDetails=true'.format(response.body['feedId']),
                    headers={
                        "Accept": "application/json",
                        "WM_CONSUMER.ID": self.walmart_consumer_id,
                        "WM_SVC.NAME": self.walmart_svc_name,
                        "WM_QOS.CORRELATION_ID": self.walmart_qos_correlation_id,
                        "WM_SVC.VERSION": self.walmart_version,
                        "WM_SVC.ENV": self.walmart_environment,
                        "WM_SEC.AUTH_SIGNATURE": walmart_api_signature["signature"],
                        "WM_SEC.TIMESTAMP": int(walmart_api_signature["timestamp"])
                    }
                )
                '''''''''''''''''''''''''''''''''''
                    Check feed status end
                '''''''''''''''''''''''''''''''''''
                return Response(response.body)
            else:
                return Response(xmltodict(response.body))
        except Exception as e:
            print e
            return Response({'data': "Failed to invoke Walmart API - invalid request data"})

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class ItemsUpdateWithXmlFileByWalmartApiViewSet(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    Pay attention to the field names: if you send multiple groups, name them like this:
    <br/>
    <pre>
    {
      "server_name": "server_name1", "request_url_1": "http://some_url_1", "request_method_1": "POST", "xml_file_to_upload_1": "/path_to_file_1",
      "server_name": "server_name2", "request_url_2": "http://some_url_2", "request_method_2": "POST", "xml_file_to_upload_2": "/path_to_file_2",
      "server_name": "server_name3", "request_url_3": "http://some_url_3", "request_method_2": "POST", "xml_file_to_upload_3": "/path_to_file_3",
      ...
    }
    </pre>
    """

    serializer_class = WalmartApiItemsWithXmlFileRequestSerializer
    parser_classes = (FormParser, MultiPartParser,)

    """
    Walmart API credential info
    """

    walmart_consumer_id = "a8bab1e0-c18c-4be7-b47a-0411153b7514"
    walmart_private_key = "MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBALBpb58mZiP4VHwx6R7fbPd/u7T22eE7vxECjsS6QHulIN/DExLSFIUrKzHgM11hm7ElRh35cKLcBR/XXZw6u/FTzFQbCiRmuDnJyz53PZi/YjhGTD2GY7jIqVILBz30J/3HRnPx9V0nBnWEEeKBeqb3rYJqsr8k1r71Sy45xey9AgMBAAECgYBFDA+PWCU0QPc4YQSge8yXlpwueUvQF2VyT/D3WPryKjCSxDSL8kPr13ihneIc055vmGo4QzBt3fX3f4D5LBfw9YFH0u29At2p9AH4FiyejhEeQ2tWNR4+zOUiMFVxDyM03zlKAsoJcRz1USklr0J1NtRnPBY7RslXU+wnps4RVQJBAPgzIV5Uo8uT4WYrbxc+Yu4Yd8imFqvGuhZpZdeS1EsRObseZc++v360k5Dx/rJzzJqd4JmeQjMJ2Y76V62jcQsCQQC19L4WYn0EYrPuGWMMoswKmOGHlU8eg3JVooZ/ufrvb6YNjVTDHMFLhU5Netw1s2eMo927giLQXF5+7ANg5MZXAkAqBrZau6g0e2jKHQalf+nOeRQnRIBIO9EcpGIbO4B46YTF+2Kv55OTR85I18ERxGvbrmnueQ6qh7tv61HXU/p7AkAqxePBg1l8JG/DsvgTyllIzHOH2dOFisTf2Jrhf6i7jHVujiC01RejVyz3DcCiZxAagZLoN0lTzcLw9y48Ist1AkEA28Opbyzq6BZOZMvXAQ/HEOGW4CVZZ9rHOwp6JByAIHxQcvwQ++TU/118qdA1HriZTZxGE1dZwnDEa2I79ICfrg=="
    walmart_svc_name = "Walmart Marketplace"
    walmart_environment = "Walmart Marketplace"
    walmart_version = "2nd"
    walmart_qos_correlation_id = "123456abcdef"

    def _paginate_log_file_results(self, request, orig_list, paginate_by=20):
        page = int(request.GET.get('page', 1))
        paginated_list = orig_list[(page-1)*paginate_by: page*paginate_by]
        paginate_left = paginate_right = True

        if page <= 1:
            paginate_left = False

        if page*paginate_by >= len(orig_list):
            paginate_right = False

        return {'paginated_list': paginated_list, 'current_page': page,
                'paginate_right': paginate_right, 'paginate_left': paginate_left}

    def get_renderer_context(self):
        context = super(ItemsUpdateWithXmlFileByWalmartApiViewSet, self).get_renderer_context()
        context['submission_history_as_json'] = 'submission_history_as_json666'
        return context

    def list(self, request):
        start_ = datetime.datetime.now()
        print 'START!!!', start_
        with open(get_walmart_api_invoke_log(request), "a+") as myfile:
            log_history = myfile.read().splitlines()

        print '2!!!', (datetime.datetime.now() - start_).total_seconds()

        if isinstance(log_history, list):
            log_history.reverse()

        print '3!!!', (datetime.datetime.now() - start_).total_seconds()

        pagination = self._paginate_log_file_results(request, log_history)
        pagination['log'] = pagination.pop('paginated_list')

        print '4!!!', (datetime.datetime.now() - start_).total_seconds()

        return Response(pagination)

    def retrieve(self, request, pk=None):
        return self.list(request)

    @staticmethod
    def generate_walmart_api_signature(walmart_api_end_point, consumer_id, private_key, request_method, file_path):
        cmd = 'java -jar "'
        cmd += os.path.dirname(os.path.realpath(__file__))
        cmd += '/DigitalSignatureUtil-1.0.0.jar" DigitalSignatureUtil '
        cmd += '{0} {1} {2} {3} {4}'
        cmd = cmd.format(walmart_api_end_point, consumer_id, private_key, request_method, file_path)

        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.readlines()

        if not output[0].startswith("WM_SEC.AUTH_SIGNATURE:") or not output[1].startswith("WM_SEC.TIMESTAMP:"):
            return None
        walmart_api_signature = {
            "signature": output[0][len("WM_SEC.AUTH_SIGNATURE:"):-1],
            "timestamp": output[1][len("WM_SEC.TIMESTAMP:"):-1]
        }
        return walmart_api_signature

    @staticmethod
    def _extract_upc(file_):
        if hasattr(file_, 'name') and hasattr(file_, 'read'):
            content = file_.read()
        else:
            content = file_
        file_.seek(0)
        upc = re.findall(r'<productId>(.*)</productId>', content)
        if upc:
            return upc[0]

    @staticmethod
    def _group_of_files_contain_invalid_xml(*files):
        for file_ in files:
            validation_results = validate_walmart_product_xml_against_xsd(file_.read())
            file_.seek(0)
            if "error" in validation_results:
                return file_, validation_results

    def create(self, request):
        if request.POST.get('consumer_id') and request.POST.get('private_key'):
            self.walmart_consumer_id = request.POST.get('consumer_id')
            self.walmart_private_key = request.POST.get('private_key')

        request_url_pattern = 'request_url'
        request_method_pattern = 'request_method'
        xml_file_to_upload_pattern = 'xml_file_to_upload'
        # output
        output = {}
        # group the fields we received
        groupped_fields = group_params(request.data, request.FILES,
                                       [request_url_pattern, request_method_pattern, xml_file_to_upload_pattern])
        # check if we need to merge all the uploaded files into one
        if request.POST.get('submit_as_one_xml_file', None):
            # this option ("submit_as_one_xml_file") merges all the selected files of each group into a single file
            groupped_fields = group_params(request.data, request.FILES,
                                           [request_url_pattern, request_method_pattern, xml_file_to_upload_pattern])
            print('Submitting as a single XML file')
            for group_name, group_data in groupped_fields.items():
                sent_file = find_in_list(group_data, xml_file_to_upload_pattern)
                request_url = find_in_list(group_data, request_url_pattern)
                request_method = find_in_list(group_data, request_method_pattern)
                if not any(sent_file) or not any(request_method) or not any(request_url):
                    output[group_name] = {'error': 'one (or more) required params missing'}
                    continue

                if any(map(self._is_excel_file, sent_file)):
                    output[group_name] = {'error': 'it is not possible to merge Excel files'}
                    continue

                request_url = request_url[0]  # this value can only have 1 element
                request_method = request_method[0]  # this value can only have 1 element
                # there may be multiple files being uploaded at the same group - so create new sub_groups if needed
                invalid_files = ItemsUpdateWithXmlFileByWalmartApiViewSet._group_of_files_contain_invalid_xml(*sent_file)
                if invalid_files:
                    output[group_name] = {}
                    output[group_name][invalid_files[0].name] = invalid_files[1]
                    upc = self._extract_upc(invalid_files[0])
                    continue

                merged_file = merge_xml_files_into_one(*sent_file)
                print('Merged files into one: %s' % merged_file)
                merged_file = open(merged_file, 'r')
                try:
                    result_for_this_group = self.process_one_set(
                         request=request, sent_file=merged_file,
                         request_url=request_url, request_method=request_method,
                         do_not_validate_xml=True, multi_item=True)
                    output[group_name] = result_for_this_group
                except Exception, e:
                    output[group_name] = {'error': str(e)}
        else:
            print('Submitting as a bunch of files')
            for group_name, group_data in groupped_fields.items():
                sent_file = find_in_list(group_data, xml_file_to_upload_pattern)
                request_url = find_in_list(group_data, request_url_pattern)
                request_method = find_in_list(group_data, request_method_pattern)
                if not any(sent_file) or not any(request_method) or not any(request_url):
                    output[group_name] = {'error': 'one (or more) required params missing'}
                    continue
                request_url = request_url[0]  # this value can only have 1 element
                request_method = request_method[0]  # this value can only have 1 element
                # there may be multiple files being uploaded at the same group - so create new sub_groups if needed
                if len(sent_file) > 1:
                    group_name_postfix = '_file_%i'
                    for file_i, _sent_file in enumerate(sent_file):
                        new_group_name = group_name + group_name_postfix % file_i
                        try:
                            result_for_this_group = self.process_one_set(
                                request=request, sent_file=_sent_file,
                                request_url=request_url, request_method=request_method,
                                multi_item=False)
                            output[new_group_name] = result_for_this_group
                        except Exception, e:
                            output[new_group_name] = {'error': str(e)}
                else:
                    try:
                        result_for_this_group = self.process_one_set(
                            request=request, sent_file=sent_file[0],
                            request_url=request_url, request_method=request_method,
                            multi_item=False)
                        output[group_name] = result_for_this_group
                    except Exception, e:
                        output[group_name] = {'error': str(e)}
        return Response(output)

    def process_one_set(self, request, sent_file, request_url, request_method, do_not_validate_xml=False, multi_item=False):
        is_excel_file = self._is_excel_file(sent_file)
        file_extension = self._get_file_extension(sent_file)

        with open(os.path.dirname(os.path.realpath(__file__)) +
                  "/upload_file.{}".format(file_extension), "wb") as upload_file:
            if is_excel_file:
                shutil.copyfileobj(sent_file, upload_file)
            else:
                xml_data_by_list = sent_file.read()
                xml_data_by_list = xml_data_by_list.splitlines()
                for xml_row in xml_data_by_list:
                    upload_file.write((xml_row + "\n").decode("utf-8").encode("utf-8"))

        upload_file = open(os.path.dirname(os.path.realpath(__file__)) +
                           "/upload_file.{}".format(file_extension), "rb")
        product_xml_text = upload_file.read()

        if is_excel_file:
            upc = '0' * 12
        else:
            # create stat report
            upc = re.findall(r'<productId>(.*)</productId>', product_xml_text)
            if not upc:
                return {'error': 'could not find <productId> element'}
            upc = upc[0]
            # we don't use validation against XSD because it fails - instead,
            #  we assume we have checked each sub-product already
            validation_results = 'okay'
            if not do_not_validate_xml:
                validation_results = validate_walmart_product_xml_against_xsd(product_xml_text)

            if "error" in validation_results:
                return validation_results

        walmart_api_signature = self.generate_walmart_api_signature(request_url,
                                                                    self.walmart_consumer_id,
                                                                    self.walmart_private_key,
                                                                    request_method.upper(),
                                                                    "signature.txt")

        if not walmart_api_signature:
            print "Failed in generating walmart api signature."
            return {'data': "Failed in generating walmart api signature."}

        if 'v3' in request_url:
            headers = {
                "Accept": "application/xml",
                "Content-Type": "multipart/form-data",
                "Content-Length": len(product_xml_text),
                "WM_SVC.ENV": "prod",
                "WM_SVC.NAME": "Walmart Marketplace",
                "WM_QOS.CORRELATION_ID": "123456abcdef",
                "WM_CONSUMER.ID": self.walmart_consumer_id,
                "WM_CONSUMER.CHANNEL.TYPE": "85078589-e261-49e9-a1e0-3da1918a7266",
                "WM_SEC.AUTH_SIGNATURE": walmart_api_signature["signature"],
                "WM_SEC.TIMESTAMP": int(walmart_api_signature["timestamp"])
            }

            if is_excel_file:
                headers['WM_SVC_REQ_FILE_TYPE'] = 'xlsm'  # May be correct is WM_SVC.REQ_FILE_TYPE: file_extension

            # TODO: Do I need to close and reopen the file?
            upload_file = open(os.path.dirname(os.path.realpath(__file__)) +
                               "/upload_file.{}".format(file_extension), "rb")
            files = [('file', ('upload_file.{}'.format(file_extension),
                               upload_file,
                               sent_file.content_type if is_excel_file else 'application/xml'))]
            sess = requests.Session()
            req = requests.Request('POST', request_url, files=files, headers=headers)

            prepped = req.prepare()
            response = sess.send(prepped)

            response = xmltodict.parse(response.content)
        else:
            if is_excel_file:
                return {'error': 'Excel submission is allowed for v3 only'}

            response = unirest.post(
                request_url,
                headers={
                    "Accept": "application/json",
                    "WM_CONSUMER.ID": self.walmart_consumer_id,
                    "WM_SVC.NAME": self.walmart_svc_name,
                    "WM_QOS.CORRELATION_ID": self.walmart_qos_correlation_id,
                    "WM_SVC.VERSION": self.walmart_version,
                    "WM_SVC.ENV": self.walmart_environment,
                    "WM_SEC.AUTH_SIGNATURE": walmart_api_signature["signature"],
                    "WM_SEC.TIMESTAMP": int(walmart_api_signature["timestamp"])
                },
                params={"file": upload_file,}
            )

            response = response.body

        feed_id = response.get('feedId') or response.get('ns2:FeedAcknowledgement', {}).get('ns2:feedId')

        if feed_id:
            import pytz
            current_time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()  # always show TZ

            server_name = request.POST.get('server_name')
            client_ip = get_client_ip(request)

            # save uploaded XML file right away
            self._save_uploaded_xml_file(feed_id, upload_file)

            # save log
            with open(get_walmart_api_invoke_log(request), "a") as myfile:
                myfile.write(", ".join([current_time, upc, server_name, client_ip, feed_id]) + "\n")

            with open(get_walmart_api_invoke_log(request), "r") as myfile:
                response['log'] = myfile.read().splitlines()

            if isinstance(response['log'], list):
                response['log'].reverse()

                pagination = self._paginate_log_file_results(request, response['log'])
                pagination['log'] = pagination.pop('paginated_list')

                for key, value in pagination.items():
                    response[key] = value

            # create SubmissionHistory and Stats right away
            get_feed_status(
                request.user, feed_id, date=datetime.datetime.now(), server_name=server_name, client_ip=client_ip
            )

        return response

    def _save_uploaded_xml_file(self, feed_id, upload_file):
        if not os.path.exists(settings.MEDIA_ROOT):
            os.makedirs(settings.MEDIA_ROOT)

        file_extension = self._get_file_extension(upload_file)

        local_new_fname = os.path.join(settings.MEDIA_ROOT,
                                       feed_id + '_' + str(random.randint(9999, 999999)) + '.' + file_extension)
        shutil.copyfile(upload_file.name, local_new_fname)
        relative_local_new_fname = local_new_fname.replace(settings.MEDIA_ROOT, '')
        if relative_local_new_fname.startswith('/'):
            relative_local_new_fname = relative_local_new_fname[1:]
        SubmissionXMLFile.objects.create(feed_id=feed_id, xml_file=relative_local_new_fname)

    def _is_excel_file(self, upload_file):
        content_type = upload_file.content_type
        file_extension = self._get_file_extension(upload_file)

        if 'vnd.ms-excel' in content_type or 'vnd.openxmlformats-officedocument.spreadsheetml' in content_type:
            return True

        return file_extension.startswith('xl')

    def _get_file_extension(self, upload_file):
        return os.path.splitext(upload_file.name)[-1][1:]

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class ItemsUpdateWithXmlTextByWalmartApiViewSet(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = WalmartApiItemsWithXmlTextRequestSerializer

    """
    Walmart API credential info
    """

    walmart_consumer_id = "a8bab1e0-c18c-4be7-b47a-0411153b7514"
    walmart_private_key = "MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBALBpb58mZiP4VHwx6R7fbPd/u7T22eE7vxECjsS6QHulIN/DExLSFIUrKzHgM11hm7ElRh35cKLcBR/XXZw6u/FTzFQbCiRmuDnJyz53PZi/YjhGTD2GY7jIqVILBz30J/3HRnPx9V0nBnWEEeKBeqb3rYJqsr8k1r71Sy45xey9AgMBAAECgYBFDA+PWCU0QPc4YQSge8yXlpwueUvQF2VyT/D3WPryKjCSxDSL8kPr13ihneIc055vmGo4QzBt3fX3f4D5LBfw9YFH0u29At2p9AH4FiyejhEeQ2tWNR4+zOUiMFVxDyM03zlKAsoJcRz1USklr0J1NtRnPBY7RslXU+wnps4RVQJBAPgzIV5Uo8uT4WYrbxc+Yu4Yd8imFqvGuhZpZdeS1EsRObseZc++v360k5Dx/rJzzJqd4JmeQjMJ2Y76V62jcQsCQQC19L4WYn0EYrPuGWMMoswKmOGHlU8eg3JVooZ/ufrvb6YNjVTDHMFLhU5Netw1s2eMo927giLQXF5+7ANg5MZXAkAqBrZau6g0e2jKHQalf+nOeRQnRIBIO9EcpGIbO4B46YTF+2Kv55OTR85I18ERxGvbrmnueQ6qh7tv61HXU/p7AkAqxePBg1l8JG/DsvgTyllIzHOH2dOFisTf2Jrhf6i7jHVujiC01RejVyz3DcCiZxAagZLoN0lTzcLw9y48Ist1AkEA28Opbyzq6BZOZMvXAQ/HEOGW4CVZZ9rHOwp6JByAIHxQcvwQ++TU/118qdA1HriZTZxGE1dZwnDEa2I79ICfrg=="
    walmart_svc_name = "Walmart Marketplace"
    walmart_environment = "Walmart Marketplace"
    walmart_version = "2nd"
    walmart_qos_correlation_id = "123456abcdef"

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    @staticmethod
    def generate_walmart_api_signature(walmart_api_end_point, consumer_id, private_key, request_method, file_path):
        cmd = 'java -jar "'
        cmd += os.path.dirname(os.path.realpath(__file__))
        cmd += '/DigitalSignatureUtil-1.0.0.jar" DigitalSignatureUtil {0} {1} {2} {3} {4}'
        cmd = cmd.format(walmart_api_end_point, consumer_id, private_key, request_method, file_path)
        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.readlines()

        if not output[0].startswith("WM_SEC.AUTH_SIGNATURE:") or not output[1].startswith("WM_SEC.TIMESTAMP:"):
            return None

        walmart_api_signature = {
            "signature": output[0][len("WM_SEC.AUTH_SIGNATURE:"):-1],
            "timestamp": output[1][len("WM_SEC.TIMESTAMP:"):-1]
        }
        return walmart_api_signature

    def create(self, request):
        try:
            request_data = request.data

            validation_results = validate_walmart_product_xml_against_xsd(request_data["xml_content_to_upload"])

            if "error" in validation_results:
                print validation_results
                return Response(validation_results)

            walmart_api_signature = self.generate_walmart_api_signature(
                request_data["request_url"],
                self.walmart_consumer_id,
                self.walmart_private_key,
                request_data["request_method"].upper(),
                "signature.txt"
            )

            if not walmart_api_signature:
                print "Failed in generating walmart api signature."
                return Response({'data': "Failed in generating walmart api signature."})

            with open(os.path.dirname(os.path.realpath(__file__)) + "/upload_file.xml", "wb") as upload_file:
                xml_data_by_list = request_data["xml_content_to_upload"].splitlines()

                for xml_row in xml_data_by_list:
                    upload_file.write((xml_row + "\n").encode("utf-8"))

            upload_file = open(os.path.dirname(os.path.realpath(__file__)) + "/upload_file.xml", "rb")

            response = unirest.post(
                request_data["request_url"],
                headers={
                    "Accept": "application/json",
                    "WM_CONSUMER.ID": self.walmart_consumer_id,
                    "WM_SVC.NAME": self.walmart_svc_name,
                    "WM_QOS.CORRELATION_ID": self.walmart_qos_correlation_id,
                    "WM_SVC.VERSION": self.walmart_version,
                    "WM_SVC.ENV": self.walmart_environment,
                    "WM_SEC.AUTH_SIGNATURE": walmart_api_signature["signature"],
                    "WM_SEC.TIMESTAMP": int(walmart_api_signature["timestamp"])
                },
                params={
                    "file": upload_file,
                }
            )

            if type(response.body) is dict:
                return Response(response.body)
            else:
                return Response(xmltodict(response.body))
        except Exception, e:
            print e
            return Response({'data': "Failed to invoke Walmart API - invalid request data"})

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class CheckFeedStatusByWalmartApiViewSet(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    Pay attention to the field names: if you send multiple groups, name them like this:
    <br/>
    <pre>
    {
      "request_url_1": "http://some_url_1", "feed_id_1": "abc123",
      "request_url_2": "http://some_url_2", "feed_id_2": "abc123",
      "request_url_3": "http://some_url_3", "feed_id_3": "abc123",
      ...
    }
    </pre>
    """
    serializer_class = WalmartApiFeedRequestSerializer
    parser_classes = (FormParser, MultiPartParser,)

    """
    Walmart API credential info
    """

    walmart_consumer_id = "a8bab1e0-c18c-4be7-b47a-0411153b7514"
    walmart_private_key = "MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBALBpb58mZiP4VHwx6R7fbPd/u7T22eE7vxECjsS6QHulIN/DExLSFIUrKzHgM11hm7ElRh35cKLcBR/XXZw6u/FTzFQbCiRmuDnJyz53PZi/YjhGTD2GY7jIqVILBz30J/3HRnPx9V0nBnWEEeKBeqb3rYJqsr8k1r71Sy45xey9AgMBAAECgYBFDA+PWCU0QPc4YQSge8yXlpwueUvQF2VyT/D3WPryKjCSxDSL8kPr13ihneIc055vmGo4QzBt3fX3f4D5LBfw9YFH0u29At2p9AH4FiyejhEeQ2tWNR4+zOUiMFVxDyM03zlKAsoJcRz1USklr0J1NtRnPBY7RslXU+wnps4RVQJBAPgzIV5Uo8uT4WYrbxc+Yu4Yd8imFqvGuhZpZdeS1EsRObseZc++v360k5Dx/rJzzJqd4JmeQjMJ2Y76V62jcQsCQQC19L4WYn0EYrPuGWMMoswKmOGHlU8eg3JVooZ/ufrvb6YNjVTDHMFLhU5Netw1s2eMo927giLQXF5+7ANg5MZXAkAqBrZau6g0e2jKHQalf+nOeRQnRIBIO9EcpGIbO4B46YTF+2Kv55OTR85I18ERxGvbrmnueQ6qh7tv61HXU/p7AkAqxePBg1l8JG/DsvgTyllIzHOH2dOFisTf2Jrhf6i7jHVujiC01RejVyz3DcCiZxAagZLoN0lTzcLw9y48Ist1AkEA28Opbyzq6BZOZMvXAQ/HEOGW4CVZZ9rHOwp6JByAIHxQcvwQ++TU/118qdA1HriZTZxGE1dZwnDEa2I79ICfrg=="
    walmart_svc_name = "Walmart Marketplace"
    walmart_environment = "Walmart Marketplace"
    walmart_version = "2nd"
    walmart_qos_correlation_id = "123456abcdef"

    walmart_consumer_id_v3 = "dbc53e77-1991-43fe-9419-4cad6aabb472"
    walmart_private_key_v3 = "MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBAJ4AaD37NgGHk4KSE4XhiPX2k122ep6fEBtaYJe61JsPzQu++wWGH+z5vxC3KmbzYdKl18OM5Khz1vNsrsXfX912hKhM+Mm3Adw+4Vft2erVW6jFSRx/wi8NTpOGT8wnHe7d3p2o2YXfk50uVT8ytwMkaYtBGJzU3Nct8EYMA3JpAgMBAAECgYEAmFLwLIEZidP5BDJsG/BZKDe1zuzzviS/VH+HDACUo4FSPva57pNmCAKmjyjm+iW9s2UrZF1avIQhQMEQpbc6JTODoZbGCatnb6iCn/m8HjoBos5LqXeq3Nzng4CCCaEqj4e4G/X7HbgHSRNZwOGWek0qgyOona1VF6orCUjO5rkCQQDiCxIUZr5qrV5pKIFFTl5DVpJ7BbLdb/kbWcQsBk5MToxERwa1osXicN1LdDDjK1omi9X6WIswRfLAIEh+HVxDAkEAsvDmO+khpmvNHMG+C97H8++X1YeKU5wa5XeXhu54wsQaJyOD7jvhd9gWPEAFT3FbOzDK9fmO8MrVCQBMTjIh4wJAGvRlAIfL9x6bXoDVAXW56d+98euZC6zZkLhgmztZROIs+ctacnhpjnoU+XVuivhVdLlCF+tNFcGRk/WFj3xizwJAA8dilVFPDJyqMDlHMij6QASHSFMccLeTOdVUtdzDYBmUE8+EMbvB/y3pCkyv0AWsz4swPhGPGzatWQtQkTYt0QJAQ/5I3qV/mrlFVjTUIxBQ/Bsg+azRoqTpiZx+EzCHpcfUyEuwnkkJwEXLhSM49Dc4DoaKBPUzKAKKrndrCsPd1Q=="

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    @staticmethod
    def generate_walmart_api_signature(walmart_api_end_point, consumer_id, private_key, request_method, file_path):
        cmd = (
            'java -jar "' +
            os.path.dirname(os.path.realpath(__file__)) +
            '/DigitalSignatureUtil-1.0.0.jar" DigitalSignatureUtil "{0}" {1} {2} {3} {4}'
        ).format(
            walmart_api_end_point,
            consumer_id,
            private_key,
            request_method,
            file_path
        )
        p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = p.stdout.readlines()

        if not output[0].startswith("WM_SEC.AUTH_SIGNATURE:") or not output[1].startswith("WM_SEC.TIMESTAMP:"):
            return None

        walmart_api_signature = {
            "signature": output[0][len("WM_SEC.AUTH_SIGNATURE:"):-1],
            "timestamp": output[1][len("WM_SEC.TIMESTAMP:"):-1]
        }

        return walmart_api_signature

    def create(self, request):
        output = {}
        request_url_pattern = 'request_url'
        request_feed_id_pattern = "feed_id"
        groupped_fields = group_params(
            request.POST, request.FILES, [request_url_pattern, request_feed_id_pattern]
        )
        for group_name, group_data in groupped_fields.items():
            request_url = find_in_list(group_data, request_url_pattern)
            request_feed_id = find_in_list(group_data, request_feed_id_pattern)
            if not any(request_url) or not any(request_feed_id):
                output[group_name] = {'error': 'one (or more) required params missing'}
                continue
            request_url = request_url[0]  # this value can only have 1 element
            request_feed_id = request_feed_id[0]  # this value can only have 1 element
            try:
                result_for_group = self.process_one_set(request_url=request_url, request_feed_id=request_feed_id,
                                                        user=request.user)
            except Exception as e:
                output[group_name] = {'error': str(e)}
                continue
            output['feed_id'] = request_feed_id
            output[group_name] = result_for_group
        return Response(output)

    def process_one_set(self, request_url, request_feed_id, user):
        # try to get the response from the DB, if it's available
        if SubmissionResults.objects.filter(feed_id=request_feed_id):
            return json.loads(SubmissionResults.objects.filter(feed_id=request_feed_id)[0].response)

        if 'v3' in request_url:
            walmart_api_signature = self.generate_walmart_api_signature(
                request_url.format(feedId=request_feed_id),
                self.walmart_consumer_id_v3,
                self.walmart_private_key_v3,
                "GET",
                os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "signature.txt"))
            )

            response = requests.get(
                request_url.format(feedId=request_feed_id),
                headers={
                    "Accept": "application/json",
                    "WM_SVC.ENV": "prod",
                    "WM_SVC.NAME": "Walmart Marketplace",
                    "WM_QOS.CORRELATION_ID": "123456abcdef",
                    "WM_CONSUMER.ID": self.walmart_consumer_id_v3,
                    "WM_CONSUMER.CHANNEL.TYPE": "85078589-e261-49e9-a1e0-3da1918a7266",
                    "WM_SEC.AUTH_SIGNATURE": walmart_api_signature["signature"],
                    "WM_SEC.TIMESTAMP": int(walmart_api_signature["timestamp"])
                }
            )
            response = response.json()
        else:
            walmart_api_signature = self.generate_walmart_api_signature(
                request_url.format(feedId=request_feed_id),
                self.walmart_consumer_id,
                self.walmart_private_key,
                "GET",
                os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "signature.txt"))
            )

            unirest.timeout(30)
            response = unirest.get(
                request_url.format(feedId=request_feed_id),
                headers={
                    "Accept": "application/json",
                    "WM_CONSUMER.ID": self.walmart_consumer_id,
                    "WM_SVC.NAME": self.walmart_svc_name,
                    "WM_QOS.CORRELATION_ID": self.walmart_qos_correlation_id,
                    "WM_SVC.VERSION": self.walmart_version,
                    "WM_SVC.ENV": self.walmart_environment,
                    "WM_SEC.AUTH_SIGNATURE": walmart_api_signature["signature"],
                    "WM_SEC.TIMESTAMP": int(walmart_api_signature["timestamp"])
                },
            )
            response = response.body

        parts = urlparse.urlparse(request_url)
        if parts.query:
            query = urlparse.parse_qs(parts.query)
            if 'limit' not in query and 'true' in query.get('includeDetails', []):
                items_received = response.get('itemsReceived', 0)
                if items_received > 50:
                    request_url += '&limit={}'.format(items_received)
                    return self.process_one_set(request_url, request_feed_id, user)

        # load the appropriate SubmissionHistory DB record (if any)
        subm_hist = SubmissionHistory.objects.filter(feed_id=request_feed_id)
        if (len(subm_hist) == 0) or (len(subm_hist) and not subm_hist[0].client_ip):
            # if there are no DB records, or client_ip is null (not ready yet)
            response['server_name'] = 'Not available yet, check later'
            response['client_ip'] = 'Not available yet, check later'
        else:
            response['server_name'] = subm_hist[0].server_name
            response['client_ip'] = subm_hist[0].client_ip
        # add datetime of submission
        xml_file = SubmissionXMLFile.objects.filter(feed_id=request_feed_id)
        if xml_file:
            response['submitted_at'] = xml_file[0].created.isoformat()

        # save response in DB if it's successful
        if isinstance(response, dict):
            if response.get('feedStatus', None) == 'PROCESSED':
                if not SubmissionResults.objects.filter(feed_id=request_feed_id):
                    SubmissionResults.objects.create(feed_id=request_feed_id, response=json.dumps(response))
                    # sync final response statuses to items statuses table
                    sync_xml_item_statuses(results=response, feed_id=request_feed_id, user=user)

        return response

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class ValidateWalmartProductXmlTextViewSet(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = WalmartApiValidateXmlTextRequestSerializer

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    def create(self, request):
        request_data = request.data

        return Response(validate_walmart_product_xml_against_xsd(request_data["xml_content_to_validate"]))

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class ValidateWalmartProductXmlFileViewSet(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = WalmartApiValidateXmlFileRequestSerializer
    parser_classes = (FormParser, MultiPartParser,)

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    @staticmethod
    def is_multiple_files_sent(request):
        for f in request.FILES.keys():
            if f.endswith('_0') or f.endswith('_1'):
                return True

    def create(self, request):
        request_data = request.data
        request_files = request.FILES

        # TODO: it does not work if the content-type is application/x-www-form-urlencoded', is this correct?
        results = {}
        for rf_key in request_files.keys():
            rf_values = request.FILES.getlist(rf_key)
            if not rf_values:
                return ErrorResponse(error_type='', msg='file is missing').to_response()
            if len(rf_values) == 1:
                # single-file upload
                rf_content = rf_values[0].read()
                xml_content_to_validate = rf_content.decode("utf-8").encode("utf-8")
                results[rf_values[0].name] = validate_walmart_product_xml_against_xsd(xml_content_to_validate)
            else:
                # multi-file upload
                for i, file_ in enumerate(rf_values):
                    rf_content = file_.read()
                    xml_content_to_validate = rf_content.decode("utf-8").encode("utf-8")
                    results[file_.name] = validate_walmart_product_xml_against_xsd(xml_content_to_validate)

        return Response(results)

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class DetectDuplicateContentBySeleniumViewset(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = WalmartDetectDuplicateContentRequestSerializer

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    def create(self, request):
        output = {}

        sellers_search_only = True

        if not request.POST.get('detect_duplication_in_sellers_only', None):
            sellers_search_only = False

        product_url_pattern = 'product_url'
        groupped_fields = group_params(request.POST, request.FILES, [product_url_pattern])

        driver = webdriver.PhantomJS()
        driver.set_window_size(1440, 900)
        mechanize_browser = mechanize.Browser()
        mechanize_browser = initialize_browser_settings(mechanize_browser)

        for group_name, group_data in groupped_fields.items():
            product_url = find_in_list(group_data, product_url_pattern)

            if not any(product_url):
                output[group_name] = {'error': 'one (or more) required params missing'}
                continue

            product_url = product_url[0]  # this value can only have 1 element

            try:
                product_id = product_url.split("/")[-1]
                product_json = json.loads(mechanize_browser.open("http://www.walmart.com/product/api/{0}".format(product_id)).read())

                description = None

                if "product" in product_json:
                    if "mediumDescription" in product_json["product"]:
                        description = product_json["product"]["mediumDescription"]
                        description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                    if not description and "longDescription" in product_json["product"]:
                        description = product_json["product"]["longDescription"]
                        description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                if not description:
                    raise Exception('No description in product')

                if len(description) > 500:
                    description = description[:500]

                    if description.rfind(" ") > 0:
                        description = description[:description.rfind(" ")].strip()

                if sellers_search_only:
                    driver.get("https://www.google.com/shopping?hl=en")
                else:
                    # means broad search
                    driver.get("https://www.google.com/")

                if sellers_search_only:
                    input_search_text = driver.find_element_by_xpath("//input[@title='Search']")
                else:
                    input_search_text = driver.find_element_by_xpath("//input[@title='Google Search']")

                input_search_text.clear()
                input_search_text.send_keys('"' + description + '"')
                input_search_text.send_keys(Keys.ENTER)
                time.sleep(3)

                current_path = os.path.dirname(os.path.realpath(__file__))
                output_file = open(current_path + "/search_page.html", "w")
                output_file.write(unicode(driver.page_source).encode("utf-8"))
                output_file.close()

                google_search_results_page_raw_text = driver.page_source
                google_search_results_page_html_tree = html.fromstring(google_search_results_page_raw_text)

                if google_search_results_page_html_tree.xpath("//form[@action='CaptchaRedirect']"):
                    raise Exception('Google blocks search requests and claim to input captcha.')

                xpath_title = google_search_results_page_html_tree.xpath("//title")
                if xpath_title and "Error 400 (Bad Request)" in xpath_title[0].text_content():
                    raise Exception('Error 400 (Bad Request)')

                if sellers_search_only:
                    seller_block = None

                    for left_block in google_search_results_page_html_tree.xpath("//ul[@class='sr__group']"):
                        if left_block.xpath("./li[@class='sr__title sr__item']/text()")[0].strip().lower() == "seller":
                            seller_block = left_block
                            break

                    seller_name_list = None

                    if seller_block:
                        seller_name_list = seller_block.xpath(".//li[@class='sr__item']//a/text()")
                        seller_name_list = [seller for seller in seller_name_list if seller.lower() != "walmart"]

                    if not seller_name_list:
                        output[product_url] = "Unique content."
                    else:
                        output[product_url] = "Found duplicate content from other sellers: ."
                        output[product_url] += ", ".join(seller_name_list)
                else:
                    duplicate_content_links = (
                        google_search_results_page_html_tree.xpath("//div[@id='search']//cite/text()")
                    )
                    if duplicate_content_links:
                        duplicate_content_links = [
                            url for url in duplicate_content_links if "walmart.com" not in url.lower()
                        ]

                    if not duplicate_content_links:
                        output[product_url] = "Unique content."
                    else:
                        output[product_url] = "Found duplicate content from other links."

            except Exception, e:
                print e
                output[product_url] = str(e)
                continue

        driver.close()
        driver.quit()
        mechanize_browser.close()

        if output:
            return Response(output)

        return None

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class DetectDuplicateContentByMechanizeViewset(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = WalmartDetectDuplicateContentRequestSerializer

    def list(self, request):

        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    '''
    def create(self, request):
        output = {}

        sellers_search_only = False
        product_url_pattern = 'product_url'
        groupped_fields = group_params(request.POST, request.FILES, [product_url_pattern])

        for group_name, group_data in groupped_fields.items():
            product_url = find_in_list(group_data, product_url_pattern)

            if not any(product_url):
                output[group_name] = {'error': 'one (or more) required params missing'}
                continue

            product_url = product_url[0]  # this value can only have 1 element

            try:
                product_id = product_url.split("/")[-1]
                product_json = json.loads(requests.get("http://www.walmart.com/product/api/{0}".format(product_id)).text)

                description = None

                if "product" in product_json:
                    if "mediumDescription" in product_json["product"]:
                        description = product_json["product"]["mediumDescription"]
                        description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                    if not description and "longDescription" in product_json["product"]:
                        description = product_json["product"]["longDescription"]
                        description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                    if not description and "shortDescription" in product_json["product"]:
                        description = product_json["product"]["shortDescription"]
                        description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                if not description:
                    raise Exception('No description in product')

                description = description.replace('"', '')

                if len(description) > 500:
                    description = description[:500]

                    if description.rfind(" ") > 0:
                        description = description[:description.rfind(" ")].strip()

                proxy = random.choice(FREE_PROXY_IP_PORT_LIST)

                results = None

                if sellers_search_only:
                    results = json.loads(requests.get('http://{0}/google_search?query="{1}"&sellers_search_only=true'.format(proxy, description)).text)
                else:
                    #means broad search
                    results = json.loads(requests.get('http://{0}/google_search?query="{1}"'.format(proxy, description)).text)

                if results["success"] == 1:
                    output[product_url] = results["message"]
                else:
                    output[product_url] = "Found duplicate content from other links."
#                    raise Exception(results["message"])
            except Exception, e:
                print e
                output[product_url] = str(e)

        if output:
            return Response(output)

        return None
    '''

    def create(self, request):
        output = {}

        sellers_search_only = True

        if not request.POST.get('detect_duplication_in_sellers_only', None):
            sellers_search_only = False

        product_url_pattern = 'product_url'
        groupped_fields = group_params(request.POST, request.FILES, [product_url_pattern])

        search_url = "http://www.google.com/search?oe=utf8&ie=utf8&source=uds&start=0&hl=en&q={0}"
        proxy_host = "proxy_out.contentanalyticsinc.com"
        proxy_port = "60000"
        proxies = {"http": "http://{}:{}/".format(proxy_host, proxy_port)}
        retry_number = 3
        word_search_limit = 10

        for group_name, group_data in groupped_fields.items():
            product_url = find_in_list(group_data, product_url_pattern)

            if not any(product_url):
                output[group_name] = {'error': 'one (or more) required params missing'}
                continue

            product_url = product_url[0]  # this value can only have 1 element
            short_description = long_description = ""

            try:
                product_json = json.loads(
                    requests.get("http://chscraper.contentanalyticsinc.com/get_data?url={0}".format(product_url)).text
                )

                if product_json["product_info"]["description"]:
                    short_description = product_json["product_info"]["description"]

                if product_json["product_info"]["long_description"]:
                    long_description = product_json["product_info"]["long_description"]

                if short_description:
                    short_description = short_description.replace("<", " <")
                    short_description = html.fromstring("<html>" + short_description + "</html>").text_content().strip()
                    short_description = short_description.replace('"', '')
                    cursor = short_description.find(" ", 0)
                    word_count = 0

                    while cursor >= 0:
                        relative_index = cursor + 1

                        if relative_index >= len(short_description):
                            break

                        for index in range(relative_index, len(short_description)):
                            if short_description[relative_index] != " ":
                                break

                        cursor = short_description.find(" ", relative_index)
                        word_count += 1

                        if word_count >= word_search_limit:
                            short_description = short_description[:cursor].strip()
                            break

                    short_description = '"' + short_description + '"'

                if long_description:
                    if long_description.startswith("<b>"):
                        long_description = long_description[long_description.find("</b>") + 4:]

                    long_description = long_description.replace("<", " <")
                    long_description = html.fromstring("<html>" + long_description + "</html>").text_content().strip()
                    long_description = long_description.replace('"', '')
                    cursor = long_description.find(" ", 0)
                    word_count = 0

                    while cursor >= 0:
                        relative_index = cursor + 1

                        if relative_index >= len(long_description):
                            break

                        for index in range(relative_index, len(long_description)):
                            if long_description[relative_index] != " ":
                                break

                        cursor = long_description.find(" ", relative_index)
                        word_count += 1

                        if word_count >= word_search_limit:
                            long_description = long_description[:cursor].strip()
                            break

                    long_description = '"' + long_description + '"'
                elif product_json["product_info"]["description"]:
                    description_block = html.fromstring(product_json["product_info"]["description"])

                    if len(description_block.xpath("./p")) > 1:
                        description_block = description_block.xpath("./p/text()")[1].strip()
                        description_block = description_block.replace('"', '')
                        cursor = description_block.find(" ", 0)
                        word_count = 0

                        while cursor >= 0:
                            relative_index = cursor + 1

                            if relative_index >= len(description_block):
                                break

                            for index in range(relative_index, len(description_block)):
                                if description_block[relative_index] != " ":
                                    break

                            cursor = description_block.find(" ", relative_index)
                            word_count += 1

                            if word_count >= word_search_limit:
                                description_block = description_block[:cursor].strip()
                                break

                        long_description = '"' + description_block + '"'

                if not short_description and not long_description:
                    raise Exception('No description in product')
            except Exception, e:
                # output[product_url] = str(e)
                output[product_url] = "Found duplicate content from other links."
                continue

            description_list = []

            if short_description:
                description_list.append(short_description)

            if long_description:
                description_list.append(long_description)

            is_duplicated = False
            google_search_fail_count = 0

            for description in description_list:
                for retry_index in range(retry_number):
                    try:
                        input_search_text = None
                        google_search_results_page_raw_text = None
                        '''
                        if sellers_search_only:
                            mechanize_browser.open("https://www.google.com/shopping?hl=en")
                            mechanize_browser.select_form('f')
                            mechanize_browser.form['q'] = '"{0}"'.format(description)
                            mechanize_browser.submit()
                        else:
                            #means broad search
                            mechanize_browser.open("https://www.google.com/")
                            mechanize_browser.select_form('f')
                            mechanize_browser.form['q'] = '"{0}"'.format(description)
                            mechanize_browser.submit()

                        google_search_results_page_raw_text = mechanize_browser.response().read()
                        '''

                        google_search_results_page_raw_text = requests.get(
                            search_url.format(urllib.quote(description.encode("utf-8"))),
                            proxies=proxies
                        ).text
                        google_search_results_page_html_tree = html.fromstring(google_search_results_page_raw_text)

                        if google_search_results_page_html_tree.xpath("//form[@action='CaptchaRedirect']"):
                            raise Exception('Google blocks search requests and claim to input captcha.')

                        xpath_title = google_search_results_page_html_tree.xpath("//title")
                        if xpath_title and "Error 400 (Bad Request)" in xpath_title[0].text_content():
                            raise Exception('Error 400 (Bad Request)')

                        if sellers_search_only:
                            '''
                            seller_block = None

                            for left_block in google_search_results_page_html_tree.xpath("//ul[@class='sr__group']"):
                                if left_block.xpath("./li[@class='sr__title sr__item']/text()")[0].strip().lower() == "seller":
                                    seller_block = left_block
                                    break

                            seller_name_list = None

                            if seller_block:
                                seller_name_list = seller_block.xpath(".//li[@class='sr__item']//a/text()")
                                seller_name_list = [seller for seller in seller_name_list if seller.lower() != "walmart"]

                            if not seller_name_list:
                                output[product_url] = "Unique content."
                            else:
                                output[product_url] = "Found duplicate content from other sellers: ." + ", ".join(seller_name_list)
                            '''
                        else:
                            duplicate_content_links = (
                                google_search_results_page_html_tree.xpath("//div[@id='search']//cite/text()")
                            )

                            no_results_text = "No results found for {0}".format(description)
                            if no_results_text in google_search_results_page_html_tree.text_content():
                                duplicate_content_links = None
                            if duplicate_content_links:
                                duplicate_content_links = [
                                    url for url in duplicate_content_links if "walmart.com" not in url.lower()
                                ]
                            if duplicate_content_links:
                                is_duplicated = True
                                break

                        break
                    except Exception, e:
                        google_search_fail_count += 1
                        print e
                        continue

                if is_duplicated:
                    break

            if is_duplicated or google_search_fail_count == retry_number * len(description_list):
                output[product_url] = "Found duplicate content from other links."
            else:
                output[product_url] = "Unique content."

        if output:
            return Response(output)

        return None

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class DetectDuplicateContentFromCsvFilesByMechanizeViewset(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = WalmartDetectDuplicateContentFromCsvFileRequestSerializer

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    def create(self, request):
        product_url_list = None

        try:
            request_data = request.data
            request_files = request.FILES
            product_url_list = request_files["csv_file_to_check"].read().splitlines()
        except Exception, e:
            print e
            return Response({'data': "Invalid csv format."})

        output = {}

        sellers_search_only = True

        if not request.POST.get('detect_duplication_in_sellers_only', None):
            sellers_search_only = False

        product_url_pattern = 'product_url'
        groupped_fields = group_params(request.POST, request.FILES, [product_url_pattern])

        mechanize_browser = mechanize.Browser()
        mechanize_browser = initialize_browser_settings(mechanize_browser)

        # mechanize_browser.add_password(url, "test", "test1234")

        for product_url in product_url_list:
            retry_number = 0

            while True:
                try:
                    retry_number += 1
                    mechanize_browser.set_proxies(random.choice(FREE_PROXY_IP_PORT_LIST))

                    # mechanize_browser.set_proxies({"http": "107.151.152.218:80"})

                    product_id = product_url.split("/")[-1]
                    product_json = json.loads(
                        mechanize_browser.open(
                            "http://www.walmart.com/product/api/{0}".format(product_id),
                            timeout=3.0
                        ).read()
                    )

                    description = None

                    if "product" in product_json:
                        if "mediumDescription" in product_json["product"]:
                            description = product_json["product"]["mediumDescription"]
                            description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                        if not description and "longDescription" in product_json["product"]:
                            description = product_json["product"]["longDescription"]
                            description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                    if not description:
                        raise Exception('No description in product')

                    if len(description) > 500:
                        description = description[:500]

                        if description.rfind(" ") > 0:
                            description = description[:description.rfind(" ")].strip()

                    input_search_text = None
                    google_search_results_page_raw_text = None

                    mechanize_browser.set_proxies(random.choice(FREE_PROXY_IP_PORT_LIST))

                    if sellers_search_only:
                        mechanize_browser.open("https://www.google.com/shopping?hl=en", timeout=3.0)
                        mechanize_browser.select_form('f')
                        mechanize_browser.form['q'] = '"{0}"'.format(description)
                        mechanize_browser.submit()
                    else:
                        # means broad search
                        mechanize_browser.open("https://www.google.com/", timeout=3.0)
                        mechanize_browser.select_form('f')
                        mechanize_browser.form['q'] = '"{0}"'.format(description)
                        mechanize_browser.submit()

                    google_search_results_page_raw_text = mechanize_browser.response().read()

                    current_path = os.path.dirname(os.path.realpath(__file__))
                    output_file = open(current_path + "/search_page.html", "w")
                    output_file.write(google_search_results_page_raw_text.decode("utf-8").encode("utf-8"))
                    output_file.close()

                    google_search_results_page_html_tree = html.fromstring(google_search_results_page_raw_text)

                    if google_search_results_page_html_tree.xpath("//form[@action='CaptchaRedirect']"):
                        raise Exception('Google blocks search requests and claim to input captcha.')

                    xpath_title = google_search_results_page_html_tree.xpath("//title")
                    if xpath_title and "Error 400 (Bad Request)" in xpath_title[0].text_content():
                        raise Exception('Error 400 (Bad Request)')

                    if sellers_search_only:
                        seller_block = None

                        for left_block in google_search_results_page_html_tree.xpath("//ul[@class='sr__group']"):
                            item_text = left_block.xpath("./li[@class='sr__title sr__item']/text()")[0]
                            if item_text.strip().lower() == "seller":
                                seller_block = left_block
                                break

                        seller_name_list = None

                        if seller_block:
                            seller_name_list = seller_block.xpath(".//li[@class='sr__item']//a/text()")
                            seller_name_list = [seller for seller in seller_name_list if seller.lower() != "walmart"]

                        if not seller_name_list:
                            output[product_url] = "Unique content."
                        else:
                            output[product_url] = "Found duplicate content from other sellers: ."
                            output[product_url] += ", ".join(seller_name_list)
                    else:
                        duplicate_content_links = (
                            google_search_results_page_html_tree.xpath("//div[@id='search']//cite/text()")
                        )

                        if duplicate_content_links:
                            duplicate_content_links = [
                                url for url in duplicate_content_links if "walmart.com" not in url.lower()
                            ]

                        if not duplicate_content_links:
                            output[product_url] = "Unique content."
                        else:
                            output[product_url] = "Found duplicate content from other links."

                    break
                except Exception, e:
                    print e
                    output[product_url] = str(e)

                    current_path = os.path.dirname(os.path.realpath(__file__))
                    output_file = open(current_path + "/search_page.html", "a")
                    output_file.write(str(e))
                    output_file.close()

                    if retry_number > 10:
                        break

                    continue

        mechanize_browser.close()

        if output:
            return Response(output)

        return None

    '''
    def create(self, request):
        output = {}

        sellers_search_only = True

        if not request.POST.get('detect_duplication_in_sellers_only', None):
            sellers_search_only = False

        product_url_pattern = 'product_url'
        groupped_fields = group_params(request.POST, request.FILES, [product_url_pattern])

        mechanize_browser = mechanize.Browser()
        mechanize_browser = initialize_browser_settings(mechanize_browser)

        for group_name, group_data in groupped_fields.items():
            product_url = find_in_list(group_data, product_url_pattern)

            if not any(product_url):
                output[group_name] = {'error': 'one (or more) required params missing'}
                continue

            product_url = product_url[0]  # this value can only have 1 element

            try:
                product_id = product_url.split("/")[-1]
                product_json = json.loads(mechanize_browser.open("http://www.walmart.com/product/api/{0}".format(product_id)).read())

                description = None

                if "product" in product_json:
                    if "mediumDescription" in product_json["product"]:
                        description = product_json["product"]["mediumDescription"]
                        description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                    if not description and "longDescription" in product_json["product"]:
                        description = product_json["product"]["longDescription"]
                        description = html.fromstring("<html>" + description + "</html>").text_content().strip()

                if not description:
                    raise Exception('No description in product')

                if len(description) > 500:
                    description = description[:500]

                    if description.rfind(" ") > 0:
                        description = description[:description.rfind(" ")].strip()

                input_search_text = None

                google_search_results_page_raw_text = None

                if sellers_search_only:
                    mechanize_browser.open("https://www.google.com/shopping?hl=en")
                    mechanize_browser.select_form('f')
                    mechanize_browser.form['q'] = '"{0}"'.format(description)
                    mechanize_browser.submit()
                else:
                    #means broad search
                    mechanize_browser.open("https://www.google.com/")
                    mechanize_browser.select_form('f')
                    mechanize_browser.form['q'] = '"{0}"'.format(description)
                    mechanize_browser.submit()

                google_search_results_page_raw_text = mechanize_browser.response().read()

                current_path = os.path.dirname(os.path.realpath(__file__))
                output_file = open(current_path + "/search_page.html", "w")
                output_file.write(google_search_results_page_raw_text.decode("utf-8").encode("utf-8"))
                output_file.close()

                google_search_results_page_html_tree = html.fromstring(google_search_results_page_raw_text)

                if google_search_results_page_html_tree.xpath("//form[@action='CaptchaRedirect']"):
                    raise Exception('Google blocks search requests and claim to input captcha.')

                if google_search_results_page_html_tree.xpath("//title") and \
                                "Error 400 (Bad Request)" in google_search_results_page_html_tree.xpath("//title")[0].text_content():
                    raise Exception('Error 400 (Bad Request)')

                if sellers_search_only:
                    seller_block = None

                    for left_block in google_search_results_page_html_tree.xpath("//ul[@class='sr__group']"):
                        if left_block.xpath("./li[@class='sr__title sr__item']/text()")[0].strip().lower() == "seller":
                            seller_block = left_block
                            break

                    seller_name_list = None

                    if seller_block:
                        seller_name_list = seller_block.xpath(".//li[@class='sr__item']//a/text()")
                        seller_name_list = [seller for seller in seller_name_list if seller.lower() != "walmart"]

                    if not seller_name_list:
                        output[product_url] = "Unique content."
                    else:
                        output[product_url] = "Found duplicate content from other sellers: ." + ", ".join(seller_name_list)
                else:
                    duplicate_content_links = google_search_results_page_html_tree.xpath("//div[@id='search']//cite/text()")

                    if duplicate_content_links:
                        duplicate_content_links = [url for url in duplicate_content_links if "walmart.com" not in url.lower()]

                    if not duplicate_content_links:
                        output[product_url] = "Unique content."
                    else:
                        output[product_url] = "Found duplicate content from other links."

            except Exception, e:
                print e
                output[product_url] = str(e)
                continue

        mechanize_browser.close()

        if output:
            return Response(output)

        return None
    '''

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class CheckItemStatusByProductIDViewSet(viewsets.ViewSet):
    """
    API endpoint for checking item's status by product identifier (SKU, GTIN, etc).
    Separate numbers by comma or space.
    Numbers should contain only digits.
    Examples:
    <br/>
    <pre>
    {
      "numbers": "0012345678, 014568321 012958473 0943846733, 049583784532"
    }
    </pre>
    """
    serializer_class = CheckItemStatusByProductIDSerializer
    # parser_classes = (FormParser)

    def list(self, request):
        return Response()

    """
    def retrieve(self, request, pk=None):
        if os.path.isfile(get_walmart_api_invoke_log(request)):
            with open(get_walmart_api_invoke_log(request)) as myfile:
                log_history = myfile.read().splitlines()
        else:
            log_history = None

        if isinstance(log_history, list):
            log_history.reverse()

        return Response({'log': log_history})
    """

    def create(self, request):
        serializer = self.serializer_class(data=parse_data(request.data))

        if serializer.is_valid():
            try:
                result = {}
                numbers = serializer.data["numbers"]
                numbers = re.split('[, \n]+', numbers)
                numbers = [n.strip() for n in numbers if n.strip()]
                for number in numbers:
                    metadata = ItemMetadata.objects.filter(upc=number).order_by('-item__when')
                    if number not in result:
                        result[number] = {}
                    for md in metadata:
                        result[number][md.item.when.isoformat()] = {
                            'datetime': md.item.when.isoformat(),
                            'status': md.item.status,
                            'product_id': md.upc,
                            'feed_id': md.feed_id
                        }
                    if not result[number]:
                        result[number] = 'NOT FOUND'
                return Response(result)
            except Exception as e:
                print str(e)

        return Response({'data': 'NO OK'})

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class ListItemsWithErrorViewSet(viewsets.ViewSet):
    """
    API endpoint for list all items that have errors
    """
    page_size = 20
    permission_classes = (permissions.AllowAny,)
    serializer_class = ListItemsWithErrorSerializer

    raw_query = (
        'SELECT '
        '{0} '
        'FROM "statistics_submitxmlitem" '
        'INNER JOIN "statistics_itemmetadata" '
                    'ON ( "statistics_submitxmlitem"."id" = "statistics_itemmetadata"."item_id" ) '
        'INNER JOIN "walmart_api_submissionresults" '
                    'ON ("walmart_api_submissionresults"."feed_id" = "statistics_itemmetadata"."feed_id") '
        'WHERE "statistics_submitxmlitem"."status" = \'failed\' AND "statistics_itemmetadata"."id" IS NOT NULL '
        '{1} '
        '{2} '
    )
    raw_query_fields = (
        '"statistics_submitxmlitem"."user_id", '
        '"statistics_submitxmlitem"."auth", '
        '"statistics_submitxmlitem"."status", '
        '"statistics_submitxmlitem"."when", '
        '"statistics_submitxmlitem"."multi_item", '
        '"statistics_itemmetadata"."item_id", '
        '"statistics_itemmetadata"."upc", '
        '"statistics_itemmetadata"."feed_id", '
        '"walmart_api_submissionresults"."response" '
    )
    raw_query_orderby = 'ORDER BY "statistics_submitxmlitem"."when" DESC'

    def _dictfetchall(self, cursor):
        # Return all rows from a cursor as a dict
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    def list(self, request):
        params = {}
        for key, value in request.query_params.iteritems():
            params[key] = value
        params.setdefault('page', 1)
        params.setdefault('as_excel', False)
        serializer = self.serializer_class(data=parse_data(params))

        if not serializer.is_valid():
            return Response({'errors': serializer.errors})

        return_excel = serializer.data["as_excel"]
        page = serializer.data["page"]

        total_query = self.raw_query.format('count(*) as cnt', '', '')
        with connection.cursor() as cursor:
            cursor.execute(total_query)
            total_result = self._dictfetchall(cursor)
            total = total_result[0]['cnt']
        start = (page-1) * self.page_size
        paging_param = 'LIMIT {} OFFSET {}'.format(self.page_size, start)
        data_query = self.raw_query.format(self.raw_query_fields, self.raw_query_orderby, paging_param)
        with connection.cursor() as cursor:
            cursor.execute(data_query)
            data = self._dictfetchall(cursor)

        items = []
        for raw_item in data:
            feed_id = raw_item['feed_id']
            sku = raw_item['upc']
            item = {
                'feed_id': feed_id,
                'sku': sku,
                'dt': raw_item['when'].strftime('%Y-%m-%d %H:%M:%S'),
            }

            try:
                parsed = json.loads(raw_item['response'])
            except (ValueError, TypeError):
                logger.warning('item["response"] not json')
                parsed = {}
            item['server'] = parsed.get('server_name', 'Not found')
            items_details = parsed.get('itemDetails', {}).get('itemIngestionStatus', [])
            for details in items_details:
                if details.get('sku') == sku:
                    item['ingestion_status'] = details['ingestionStatus']
                    item['ingestion_errors'] = json.dumps(details['ingestionErrors'])
                    break
            else:
                # if item with needed sku not found don't append it
                logger.error('Product sku={0} not found in results for feed_id={1}'.format(sku, feed_id))
                continue
            items.append(item)
        if not return_excel:
            return Response({'items': items, 'page_size': self.page_size, 'total': total, 'current_page': page})
        else:
            output = StringIO.StringIO()
            book = Workbook(output, {'remove_timezone': True})
            sheet = book.add_worksheet('results')

            headers = ('SKU', 'FEED ID', 'Server', 'Ingestion Status', 'Ingestion Errors', 'Submitted at')
            for i, header in enumerate(headers):
                sheet.write(0, i, header)
            for i, row in enumerate(items, start=1):
                sheet.write(i, 0, row['sku'])
                sheet.write(i, 1, row['feed_id'])
                sheet.write(i, 2, row['server'])
                sheet.write(i, 3, row['ingestion_status'])
                sheet.write(i, 4, row['ingestion_errors'])
                sheet.write(i, 5, row['dt'])

            book.close()
            output.seek(0)

            response = HttpResponse(
                FileWrapper(output),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="%s"' % 'results.xlsx'
            return response


class DetailedViewViewSet(RestFrameworkViewSetRendererTemplateNameMixin, viewsets.ViewSet):
    """
    API endpoint for list item details
    """
    permission_classes = (permissions.AllowAny,)
    serializer_class = FeedDetailsSerializer
    parser_classes = (FormParser, MultiPartParser,)
    http_method_names = ['get', 'post']
    template_name = 'rest_framework/detailed_view.html'

    def list(self, _):
        return Response({})

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        # return_excel = serializer.data["as_excel"]
        if not serializer.is_valid():
            errors = ['{}: {}'.format(k, '; '.join(v)) for k, v in serializer.errors.iteritems()]
            return Response({'errors': errors}, status=400)

        request_url = serializer.validated_data['request_url']
        request_feed_id = serializer.validated_data['feed_id']
        request_feed_id = request_feed_id.split('/')[-1]
        try:
            result = self.process_one_set(request_url=request_url, request_feed_id=request_feed_id, user=request.user)
        except Exception as e:
            return Response({'errors': {'Processing error': str(e)}})
        items = []
        if result:
            items = result.get('itemDetails', {}).get('itemIngestionStatus', [])

        as_excel = serializer.validated_data['as_excel']
        if not as_excel:
            output = dict()
            output['items'] = items
            output['feed_id'] = serializer.validated_data['feed_id']
            return Response(output)
        else:
            output = StringIO.StringIO()
            book = Workbook(output)
            sheet = book.add_worksheet('results')

            headers = ('SKU', 'Ingestion Status', 'Ingestion Errors')
            for i, header in enumerate(headers):
                sheet.write(0, i, header)
            for i, row in enumerate(items, start=1):
                sheet.write(i, 0, row['sku'])
                sheet.write(i, 1, row['ingestionStatus'])
                sheet.write(
                    i,
                    2,
                    '\n'.join(
                        [err.get('description', '')for err in row.get('ingestionErrors', {}).get('ingestionError', [])]
                    )
                )

            book.close()
            output.seek(0)

            response = HttpResponse(
                FileWrapper(output),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="%s"' % 'results.xlsx'
            return response

    def process_one_set(self, request_url, request_feed_id, user):
        # try to get the response from the DB, if it's available
        if SubmissionResults.objects.filter(feed_id=request_feed_id):
            return json.loads(SubmissionResults.objects.filter(feed_id=request_feed_id)[0].response)


class FeedIDRedirectView(DjangoView):
    def get(self, request, *args, **kwargs):
        context = {'feed_id': kwargs.get('feed_id', None)}
        context.update(csrf(request))
        return render_to_response(template_name='redirect_to_feed_check.html', context=context)


def get_feed_status(user, feed_id, date=None, process_check_feed=True, check_auth=True,
                    server_name=None, client_ip=None):
    if os.path.exists(settings.TEST_TWEAKS['item_upload_ajax_ignore']):
        # do not perform time-consuming operations - return dummy empty response
        return {}
    if check_auth and not user.is_authenticated():
        return
    # try to get data from cache
    feed_history = SubmissionHistory.objects.filter(user=user, feed_id=feed_id)
    if feed_history:
        return {
            'statuses': feed_history[0].get_statuses(),
            'ok': feed_history[0].all_items_ok(),
            'partial_success': feed_history[0].partial_success(),
            'in_progress': feed_history[0].in_progress()
        }
    # if no cache found - perform real check, update stats, and save cache
    feed_checker = CheckFeedStatusByWalmartApiViewSet()
    check_results = feed_checker.process_one_set(
        'https://marketplace.walmartapis.com/v2/feeds/{feedId}?includeDetails=true',
        feed_id,
        user
    )
    if process_check_feed and date:
        process_check_feed_response(user, check_results, date=date, check_auth=check_auth)

    ingestion_statuses = check_results.get('itemDetails', {}).get('itemIngestionStatus', [])
    for result_stat in ingestion_statuses:
        subm_stat = result_stat.get('ingestionStatus', None)
        if subm_stat and isinstance(subm_stat, (str, unicode)):
            db_history = SubmissionHistory.objects.create(
                user=user, feed_id=feed_id, server_name=server_name, client_ip=client_ip
            )
            db_history.set_statuses([subm_stat])
    if not ingestion_statuses:
        if check_results.get('feedStatus', '').lower() == 'error':
            db_history = SubmissionHistory.objects.create(
                user=user, feed_id=feed_id, server_name=server_name, client_ip=client_ip
            )
            db_history.set_statuses(['error'])
    feed_history = SubmissionHistory.objects.filter(user=user, feed_id=feed_id)
    if feed_history:
        return {
            'statuses': feed_history[0].get_statuses(),
            'ok': feed_history[0].all_items_ok(),
            'partial_success': feed_history[0].partial_success(),
            'in_progress': feed_history[0].in_progress()
        }
    return {}


class FeedStatusAjaxView(DjangoView):
    def get(self, request, *args, **kwargs):
        feed_id = kwargs['feed_id']

        if not request.user.is_authenticated():
            return JsonResponse({})

        feed_history = SubmissionHistory.objects.filter(user=request.user,
                                                        feed_id=feed_id)
        if feed_history:
            return JsonResponse({
                'statuses': feed_history[0].get_statuses(),
                'ok': feed_history[0].all_items_ok(),
                'partial_success': feed_history[0].partial_success(),
                'in_progress': feed_history[0].in_progress()
            })

        return JsonResponse({})


class XMLFileRedirect(DjangoView):
    def get(self, request, *args, **kwargs):
        feed_id = kwargs['feed_id']

        if not request.user.is_authenticated():
            return HttpResponse('Error: not logged in')

        xml_file = SubmissionXMLFile.objects.filter(feed_id=feed_id)
        if len(xml_file) > 2:
            return HttpResponse('Error: Multiple XML files found for feed ID ' + feed_id)
        elif len(xml_file) == 0:
            return HttpResponse('Error: File not found for feed ID ' + feed_id)
        else:
            return HttpResponseRedirect(settings.MEDIA_URL + str(xml_file[0].xml_file))


class ToolIDViewSet(viewsets.ViewSet):
    """
    API endpoint for getting Tool ID from Walmart by UPC.
    Separate UPCs by comma or space.
    Examples:
    <br/>
    <pre>
    {
      "api_key": "0123456789",
      "upcs": "852905005945, 852905005549, 852905005815, 887530004889, 704660921797"
    }
    </pre>
    """
    permission_classes = (permissions.IsAuthenticated,)

    serializer_class = ToolIDSerializer

    WALMART_API_URL_TEMPLATE = 'http://api.walmartlabs.com/v1/items?apiKey={api_key}&upc={upc}'

    def list(self, request):
        return Response()

    def create(self, request):
        serializer = self.serializer_class(data=parse_data(request.data))

        if serializer.is_valid():
            try:
                detailed = serializer.data['detailed']

                results = []

                if detailed:
                    results.append(('upc', 'itemId', 'name', 'brandName', 'stock'))
                else:
                    results.append(('UPC', 'Tool ID'))

                upcs = [upc.strip() for upc in re.split('[, \n]+', serializer.data['upcs'])]

                for upc in upcs:
                    item = self._get_item(serializer.data['api_key'], upc) or {}
                    item_id = item.get('itemId') or 'NOT FOUND'
                    name = item.get('name') or ''
                    brand = item.get('brandName') or ''
                    stock = item.get('stock') or ''

                    if detailed:
                        results.append((upc, item_id, name, brand, stock))
                    else:
                        results.append((upc, item_id))

                if request.content_type.split(';')[0].strip() == 'application/json':
                    if detailed:
                        return Response(dict(map(lambda (upc, item_id, name, brand, stock):
                                                 (upc, {'item_id': item_id,
                                                        'name': name,
                                                        'brand': brand,
                                                        'stock': stock}),
                                                 results[1:])))
                    else:
                        return Response(dict(results[1:]))
                else:
                    csv_writer = csv.writer(type('Echo', (object,), {'write': lambda self, x: x})())

                    response = HttpResponse((csv_writer.writerow(x) for x in results), content_type='text/csv')
                    response['Content-Disposition'] = 'attachment;filename=tool_ids.csv'

                    return response
            except Exception as e:
                print str(e)
        else:
            return Response(status=400)

    def _get_item(self, api_key, upc):
        url = self.WALMART_API_URL_TEMPLATE.format(api_key=api_key, upc=upc)

        response = requests.get(url)

        if response.status_code == requests.codes.ok:
            items = response.json().get('items')

            if items:
                return items[0]
        else:
            print 'ERROR: api_key={}, upc={}\n{}'.format(api_key, upc, response.content)


class RichMediaViewSet(viewsets.ViewSet):
    """
    API endpoint to generate Rich Media XML for submission to Walmart

    Mode specifies the process mode for the specified modules associated with this item.
    This attribute can be specified to be one of the following:

    1) mode=MERGE
    This will merge the new set of modules specified here with the existing set of modules in the Mart.

    If a module currently exists in the Mart and it is not specified here, the module existing in the Mart continues to exist.
    If a module currently exists in the Mart and it is specified here, the module specified here replaces the one in the Mart.
    If a module currently does not exist in the Mart and it is specified here, it is inserted.
    If a module currently does not exist in the Mart and it is not specified here, no action is taken for that module.

    In other words, the modules specified for this item are
        1) inserted, if absent in the Mart OR
        2) replaced, if already present in the Mart

    2) mode=REPLACE
    This will replace entire set of modules associated with this item in the Mart with the set of modules
    specified here. The new set of modules may be more or less in number than what was existing earlier.

    3) mode=DELETE
    This will delete the entire set of modules associated with this item in the Mart.
    If any module is specified with this DELETE mode (with or without content), the module specification
    will be completely ignored.

    """
    permission_classes = (permissions.IsAuthenticated,)

    serializer_class = RichMediaSerializer

    def list(self, request):
        return Response()

    def create(self, request):
        serializer = self.serializer_class(data=parse_data(request.data))

        if serializer.is_valid():
            try:
                marketing_content = serializer.data['marketing_content']

                self._save_marketing_content(marketing_content)

                context = {
                    'item_id': serializer.data['item_id'],
                    'marketing_content': marketing_content,
                    'mode': serializer.data['mode']
                }

                xml_template = loader.get_template('rich_media.xml')

                response = HttpResponse(xml_template.render(context), content_type='text/xml')
                response['Content-Disposition'] = 'attachment;filename=rich_media_{}.xml'.format(context['item_id'])

                return response
            except:
                print traceback.format_exc()

                return Response(status=500)
        else:
            return Response(status=400)

    def _save_marketing_content(self, marketing_content):
        if RichMediaMarketingContent.objects.all().first():
            RichMediaMarketingContent.objects.update(marketing_content=marketing_content)
        else:
            RichMediaMarketingContent.objects.create(marketing_content=marketing_content)
