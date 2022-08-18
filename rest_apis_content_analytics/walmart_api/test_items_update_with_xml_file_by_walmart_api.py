import json
import os
import sys

import django
import requests

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CWD)
sys.path.append(os.path.join(CWD, '..'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'rest_apis_content_analytics.settings'

django.setup()


from tests import RestAPIsTests


class FakeServerThread():
    host = 'localhost'
    port = '8000'


def assertEqual(a, b):
    assert a == b


def assertIn(a, b):
    assert a in b


if __name__ == '__main__':
    RestAPIsTests.runTest = lambda *k: k
    rt = RestAPIsTests()
    rt.setUp()
    rt.server_thread = FakeServerThread()

    rt.assertEqual = assertEqual
    rt.assertIn = assertIn

    rt.test_items_update_with_xml_file_by_walmart_api()
    rt.tearDown()