from django.test import TestCase
from middlewares import LogQueryInformation


class FilterPathTestCase(TestCase):

    def setUp(self):
        self.log_query_information = LogQueryInformation()

    def test_filter_paths(self):
        self.assertEqual(
            self.log_query_information.is_filter_path('/admin/'), True)
        self.assertEqual(
            self.log_query_information.is_filter_path('/admin/resource'), True)
        self.assertEqual(
            self.log_query_information.is_filter_path('/admin/resource/resource'), True)
        self.assertEqual(
            self.log_query_information.is_filter_path('/static/'), True)
        self.assertEqual(
            self.log_query_information.is_filter_path('/static/resource'), True)
        self.assertEqual(
            self.log_query_information.is_filter_path('/favicon.ico'), True)
        self.assertEqual(
            self.log_query_information.is_filter_path('/admin'), False)
        self.assertEqual(
            self.log_query_information.is_filter_path('/static'), False)
