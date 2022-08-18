import unittest
import mock

from pyramid import testing
import pyramid.httpexceptions as exc

from web_runner.scrapyd import ScrapydJobHelper
from web_runner.views import spider_start_view, spider_pending_view


class SpiderViewTests(unittest.TestCase):

    def setUp(self):
        self.settings = {
            'spider._names': 'spider_cfg',
            'spider._scrapyd.base_url': 'http://localhost:6800/',
            'spider._scrapyd.items_path': '',
            'db_filename': '',

            'spider.spider_cfg.resource': 'spider_resource',
            'spider.spider_cfg.spider_name': 'spider_name',
            'spider.spider_cfg.project_name': 'spider_project_name',
        }
        self.config = testing.setUp(settings=self.settings)

    def tearDown(self):
        testing.tearDown()

    def test_unknown_resource(self):
        request = testing.DummyRequest(path="/unexistant/path/")
        self.assertRaises(exc.HTTPNotFound, spider_start_view, request)

    def test_when_a_job_is_polled_but_its_unknown_then_it_should_404(self):
        request = testing.DummyRequest(
            path="/crawl/project/spider_project_name/spider/spider_name"
                 "/job/XXX/"
        )
        request.matchdict = {
            'project': 'spider_project_name',
            'spider': 'spider_name',
            'jobid': 'XXX',
        }
        request.remote_addr = ''

        with mock.patch('web_runner.views.ScrapydJobHelper') as helper_mock:
            helper_mock.JobStatus = ScrapydJobHelper.JobStatus

            helper_instace = helper_mock.return_value
            helper_instace.report_on_job.return_value = \
                ScrapydJobHelper.JobStatus.unknown

            with mock.patch('web_runner.db.DbInterface'):
                self.assertRaises(
                    exc.HTTPNotFound, spider_pending_view, request)
