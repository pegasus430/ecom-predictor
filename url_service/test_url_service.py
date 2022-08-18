from collections import OrderedDict
from itertools import count, repeat, imap, izip
import functools
import unittest
import os.path
import logging
import sqlite3
import json

import requests

import url_service


logging.basicConfig(level=logging.WARN)


URL_BASE = u'http://localhost:8080/'
URL_QUEUED_URLS = 'get_queued_urls/'
URL_SAVED_PARSED_FROM_TEXT = 'save_parsed_from_text/'
URL_URL_LOAD_FAILED = 'url_load_failed/'


class UrlServiceTest(unittest.TestCase):

    def setUp(self):
        # The database will exist since the server should be running before it
        # is tested.

        self.url_base = u'http://www.example.com/'
        self.url_paths = ['a', 'b', 'c', '']
        self.field_names = [u'url', u'id', u'imported_data_id', u'category_id',
                            u'bid']
        self.queued_urls = map(
            OrderedDict,  # Ordered so that we can also use it as a tuple.
            imap(functools.partial(zip, self.field_names),
                 izip([self.url_base + path for path in self.url_paths],
                      imap(unicode, count(1)),
                      imap(unicode, count(100, 100)),
                      imap(unicode, count(1000, 1000)),
                      repeat(u'42'))))

        self.db = sqlite3.connect(
            os.path.join(url_service.HERE, url_service.DB_FN))

        # Clear the DB.
        self.db.execute("DELETE FROM queued_url")
        self.db.execute("DELETE FROM raw_pages")
        self.db.execute("DELETE FROM load_failure")

        self.db.executemany(
            """INSERT
                INTO queued_url (url, url_id, imported_data_id, category_id)
                VALUES (?, ?, ?, ?)""",
            (data.values()[:-1] for data in self.queued_urls))  # Discard bid.
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_get_queued_urls(self):
        r = requests.get(URL_BASE + URL_QUEUED_URLS)

        self.assertEqual(200, r.status_code)
        self.assertSequenceEqual(map(dict, self.queued_urls),
                                 json.loads(r.content))

    def test_get_queued_urls_limit(self):
        r = requests.get(URL_BASE + URL_QUEUED_URLS + '?limit=2')

        self.assertEqual(200, r.status_code)
        self.assertEqual('application/json; charset=UTF-8',
                         r.headers['content-type'])
        self.assertSequenceEqual(self.queued_urls[:2], json.loads(r.content))

    def test_get_queued_urls_404(self):
        r = requests.get(URL_BASE + URL_QUEUED_URLS + '?limit=A')

        self.assertEqual(404, r.status_code)
        self.assertEqual('application/json; charset=UTF-8',
                         r.headers['content-type'])
        self.assertEqual("Limit must be a natural number, not 'A'.",
                         json.loads(r.content))

    def test_saved_parsed_from_text(self):
        r = requests.post(URL_BASE + URL_SAVED_PARSED_FROM_TEXT, {
            'url': URL_BASE,
            'id': 101,  # url_id in the database.
            'imported_data_id': 102,
            'category_id': 103,
            'text': 'this is the content',
            'info': 'this is the debug info',
        })

        self.assertEqual(200, r.status_code)

        rows = self.db.execute(
            """SELECT url, url_id, imported_data_id, category_id, text,
                      request_debug_info
               FROM raw_pages""").fetchall()
        self.assertEqual(
            [(URL_BASE, 101, 102, 103, u'this is the content',
             u'this is the debug info')],
            rows)

    def test_saved_parsed_from_text_404_key(self):
        r = requests.post(URL_BASE + URL_SAVED_PARSED_FROM_TEXT, {
            'url wrong key': URL_BASE,
            'id': 101,  # url_id in the database.
            'imported_data_id': 102,
            'category_id': 103,
            'text': 'this is the content',
            'info': 'this is the debug info',
        })

        self.assertEqual(404, r.status_code)
        self.assertEqual('application/json; charset=UTF-8',
                         r.headers['content-type'])
        self.assertEqual("Field 'url' missing from data.",
                         json.loads(r.content))

    def test_saved_parsed_from_text_404_value(self):
        r = requests.post(URL_BASE + URL_SAVED_PARSED_FROM_TEXT, {
            'url': URL_BASE,
            'id': "Not a number",  # url_id in the database.
            'imported_data_id': 102,
            'category_id': 103,
            'text': 'this is the content',
            'info': 'this is the debug info',
        })

        self.assertEqual(404, r.status_code)
        self.assertEqual('application/json; charset=UTF-8',
                         r.headers['content-type'])
        self.assertEqual("invalid literal for int() with base 10: "
                         "'Not a number'",
                         json.loads(r.content))

    def test_url_load_failed(self):
        r = requests.post(URL_BASE + URL_URL_LOAD_FAILED, {
            'id': 101,  # url_id in the database.
            'http_code': 513,
            'error_string': "this is an error msg",
        })

        self.assertEqual(200, r.status_code)

        rows = self.db.execute(
            """SELECT url_id, http_code, error_string
               FROM load_failure""").fetchall()
        self.assertEqual([(101, 513, u'this is an error msg')], rows)

    def test_url_load_failed_404_key(self):
        r = requests.post(URL_BASE + URL_URL_LOAD_FAILED, {
            'id': 101,  # url_id in the database.
            'http_code fail!': 513,
            'error_string': "this is an error msg",
        })

        self.assertEqual(404, r.status_code)
        self.assertEqual('application/json; charset=UTF-8',
                         r.headers['content-type'])
        self.assertEqual("Field 'http_code' missing from data.",
                         json.loads(r.content))

    def test_url_load_failed_404_value(self):
        r = requests.post(URL_BASE + URL_URL_LOAD_FAILED, {
            'id': 101,  # url_id in the database.
            'http_code': "four hundred and four",
            'error_string': "this is an error msg",
        })

        self.assertEqual(404, r.status_code)
        self.assertEqual('application/json; charset=UTF-8',
                         r.headers['content-type'])
        self.assertEqual("invalid literal for int() with base 10: "
                         "'four hundred and four'",
                         json.loads(r.content))


if __name__ == '__main__':
    unittest.main()
