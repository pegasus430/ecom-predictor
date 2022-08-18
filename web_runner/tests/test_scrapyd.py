# vim:fileencoding=UTF-8

from __future__ import division, absolute_import, unicode_literals
from future_builtins import *

import logging
import unittest

import mock
import pyramid.httpexceptions as exc

from web_runner.config_util import SpiderConfig
from web_runner.scrapyd import Scrapyd, ScrapydJobHelper


logging.basicConfig(level=logging.FATAL)


class ScrapydTest(unittest.TestCase):

    maxDiff = None

    URL = 'http://example.com'

    EXPECTED_LIST_JOBS_URL = URL + '/listjobs.json?project=test'
    EXPECTED_LIST_PROJECTS_URL = URL + '/listprojects.json'
    EXPECTED_LIST_SPIDERS_URL = URL + '/listspiders.json?project=test'

    EMPTY_QUEUE = {'running': 0, 'finished': 0, 'pending': 0}

    def setUp(self):
        # Always clear the cache so that tests are independent.
        Scrapyd._CACHE.clear()

        self.subject = Scrapyd(ScrapydTest.URL)

    def test_when_status_is_not_ok_then_it_should_report_an_error(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {"status": "ERROR", "message": "Test"}

            self.assertRaises(
                exc.HTTPBadGateway, self.subject.get_queues, ['test'])

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_JOBS_URL)

    def test_when_queues_are_empty_then_it_should_return_empty_queues(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {
                "status": "ok", "pending": [], "running": [], "finished": [],
            }

            queues, summary = self.subject.get_queues(['test'])

            self.assertEqual({'test': self.EMPTY_QUEUE}, queues)
            self.assertEqual(self.EMPTY_QUEUE, summary)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_JOBS_URL)

    def test_when_queues_have_jobs_then_it_should_return_their_state(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {
                "status": "ok",
                "pending": [
                    {
                        "id": "78391cc0fcaf11e1b0090800272a6d06",
                        "project_name": "spider1",
                    }
                ],
                "running": [],
                "finished": [
                    {
                        "id": "2f16646cfcaf11e1b0090800272a6d06",
                        "spider": "spider3",
                        "start_time": "2012-09-12 10:14:03.594664",
                        "end_time": "2012-09-12 10:24:03.594664"
                    }
                ],
            }

            queues, summary = self.subject.get_queues(['test'])

            expected_queue = {'running': 0, 'finished': 1, 'pending': 1}

            self.assertEqual({'test': expected_queue}, queues)
            self.assertEqual(expected_queue, summary)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_JOBS_URL)

    def test_when_a_request_is_repeated_then_it_should_query_just_once(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {
                "status": "ok", "pending": [], "running": [], "finished": [],
            }

            queues, summary = self.subject.get_queues(['test'])
            self.assertEqual({'test': self.EMPTY_QUEUE}, queues)
            self.assertEqual(self.EMPTY_QUEUE, summary)

            queues, summary = self.subject.get_queues(['test'])
            self.assertEqual({'test': self.EMPTY_QUEUE}, queues)
            self.assertEqual(self.EMPTY_QUEUE, summary)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_JOBS_URL)

    def test_when_there_are_no_project_then_it_should_get_an_empty_list(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {"status": "ok", "projects": []}

            projects = self.subject.get_projects()
            self.assertEqual([], projects)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_PROJECTS_URL)

    def test_when_there_are_projects_then_it_should_get_a_list(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {
                "status": "ok",
                "projects": [
                    "proj1",
                    "proj2",
                ],
            }

            projects = self.subject.get_projects()
            self.assertEqual(["proj1", "proj2"], projects)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_PROJECTS_URL)

    def test_when_there_are_no_jobs_then_it_should_get_an_empty_dict(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {
                "status": "ok", "pending": [], "running": [], "finished": [],
            }

            jobs = self.subject.get_jobs(['test'])

            self.assertEqual({}, jobs)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_JOBS_URL)

    def test_when_there_are_jobs_then_it_should_return_them(self):
        # Had to remove dates from jobs to make tests reliable.
        # The time conversion that's performed adds a configuration dependent
        # offset and a small, millisecond, error.
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {
                "status": "ok",
                "pending": [
                    {
                        "id": "78391cc0fcaf11e1b0090800272a6d06",
                        "project_name": "spider1",
                    }
                ],
                "running": [],
                "finished": [
                    {
                        "id": "2f16646cfcaf11e1b0090800272a6d06",
                        "spider": "spider3",
                    }
                ],
            }

            jobs = self.subject.get_jobs(['test'])

            expected = {
                '2f16646cfcaf11e1b0090800272a6d06': {
                    'id': '2f16646cfcaf11e1b0090800272a6d06',
                    'spider': 'spider3',
                    'status': 'finished',
                },
                '78391cc0fcaf11e1b0090800272a6d06': {
                    'id': '78391cc0fcaf11e1b0090800272a6d06',
                    'project_name': 'spider1',
                    'status': 'pending',
                },
            }
            self.assertEqual(expected, jobs)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_JOBS_URL)

    def test_when_there_are_no_spiders_then_it_should_get_an_empty_list(self):
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {"status": "ok", "spiders": []}

            jobs = self.subject.get_spiders('test')

            self.assertEqual([], jobs)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_SPIDERS_URL)

    def test_when_there_are_spiders_then_it_should_return_them(self):
        # Had to remove dates from jobs to make tests reliable.
        # The time conversion that's performed adds a configuration dependent
        # offset and a small, millisecond, error.
        with mock.patch('web_runner.scrapyd.requests') as mock_requests:
            response = mock_requests.get.return_value
            response.json.return_value = {
                "status": "ok",
                "spiders": ["spider1", "spider2", "spider3"],
            }

            jobs = self.subject.get_spiders('test')

            self.assertEqual(["spider1", "spider2", "spider3"], jobs)

            mock_requests.get.assert_called_once_with(
                self.EXPECTED_LIST_SPIDERS_URL)

    def test_when_scrapyd_is_down_then_it_should_make_no_further_reqs(self):
        with mock.patch('web_runner.scrapyd.requests.get') as mock_requests_get:
            response = mock_requests_get.return_value
            response.status_code = 500

            status = self.subject.get_operational_status()

            self.assertEqual(
                {
                    'scrapyd_alive': False,
                    'scrapyd_operational': False,
                    'scrapyd_projects': None,
                    'spiders': None,
                    'queues': None,
                    'summarized_queue': None,
                },
                status,
            )

            mock_requests_get.assert_called_once_with(self.URL)

    def test_when_scrapyd_fails_then_it_should_not_be_operational(self):
        with mock.patch('web_runner.scrapyd.requests.get') as mock_requests_get:
            alive_response = mock.MagicMock()
            alive_response.status_code = 200

            mock_requests_get.side_effect = [
                alive_response,
                exc.HTTPBadGateway(detail="Test"),
            ]

            status = self.subject.get_operational_status()

            self.assertEqual(
                {
                    'scrapyd_alive': True,
                    'scrapyd_operational': False,
                    'scrapyd_projects': None,
                    'spiders': None,
                    'queues': None,
                    'summarized_queue': None,
                },
                status,
            )

            mock_requests_get.assert_any_call(self.URL)
            mock_requests_get.assert_called_with(
                self.EXPECTED_LIST_PROJECTS_URL)

    def test_when_scrapyd_responds_then_it_should_provide_an_ok_status(self):
        with mock.patch('web_runner.scrapyd.requests.get') as mock_requests_get:
            alive_resp = mock.MagicMock()
            alive_resp.status_code = 200

            projects_resp = mock.MagicMock()
            projects_resp.status_code = 200
            projects_resp.json.return_value = {
                'status': 'ok',
                'projects': ['test', 'p2'],
            }

            spiders1_resp = mock.MagicMock()
            spiders1_resp.status_code = 200
            spiders1_resp.json.return_value = {
                'status': 'ok',
                'spiders': ['p1_sp1', 'p1_sp2'],
            }

            spiders2_resp = mock.MagicMock()
            spiders2_resp.status_code = 200
            spiders2_resp.json.return_value = {
                'status': 'ok',
                'spiders': ['p2_sp1', 'p2_sp2'],
            }

            jobs1_resp = mock.MagicMock()
            jobs1_resp.status_code = 200
            jobs1_resp.json.return_value = {
                'status': 'ok',
                "pending": [
                    {
                        "id": "78391cc0fcaf11e1b0090800272a6d06",
                        "project_name": "spider1",
                    }
                ],
                "running": [],
                "finished": [
                    {
                        "id": "2f16646cfcaf11e1b0090800272a6d06",
                        "spider": "spider3",
                    }
                ],

            }

            jobs2_resp = mock.MagicMock()
            jobs2_resp.status_code = 200
            jobs2_resp.json.return_value = {
                'status': 'ok',
                "pending": [
                    {
                        "id": "XXXX1cc0fcaf11e1b0090800272a6d06",
                        "project_name": "spider10",
                    }
                ],
                "finished": [],
                "running": [
                    {
                        "id": "XXXX646cfcaf11e1b0090800272a6d06",
                        "spider": "spider30",
                    }
                ],

            }

            mock_requests_get.side_effect = [
                alive_resp,
                projects_resp,
                spiders1_resp,
                spiders2_resp,
                jobs1_resp,
                jobs2_resp,
            ]

            status = self.subject.get_operational_status()

            self.assertEqual(
                {
                    'scrapyd_alive': True,
                    'scrapyd_operational': True,
                    'scrapyd_projects': ['test', 'p2'],
                    'spiders': {
                        'test': ['p1_sp1', 'p1_sp2'],
                        'p2': ['p2_sp1', 'p2_sp2'],
                    },
                    'queues': {
                        'test': {'finished': 1, 'pending': 1, 'running': 0},
                        'p2': {'finished': 0, 'pending': 1, 'running': 1},
                    },
                    'summarized_queue': {
                        'finished': 1,
                        'pending': 2,
                        'running': 1,
                    },
                },
                status,
            )

            # More requests than these are actually performed.
            mock_requests_get.assert_any_call(self.URL)
            mock_requests_get.assert_any_call(self.EXPECTED_LIST_SPIDERS_URL)
            mock_requests_get.assert_any_call(self.EXPECTED_LIST_JOBS_URL)
            mock_requests_get.assert_any_call(self.EXPECTED_LIST_PROJECTS_URL)

    def test_when_a_job_is_started_ok_then_we_return_its_id(self):
        with mock.patch('web_runner.scrapyd.requests.post') as mock_post:
            response = mock_post.return_value
            response.json.return_value = {"status": "ok", "jobid": "XXX"}

            job_id = self.subject.schedule_job('project', 'spider', {})

            self.assertEqual('XXX', job_id)


ScrapydJobHelper._VERIFICATION_DELAY = 0  # Not to waste time.


class ScrapydJobsHelperTest(unittest.TestCase):

    def test_when_starting_a_job_then_it_should_return_the_job_id(self):
        scrapyd = mock.MagicMock(spec=Scrapyd)
        scrapyd.schedule_job.return_value = "XXX"

        helper = ScrapydJobHelper(
            {ScrapydJobHelper.SCRAPYD_ITEMS_PATH: 'scrapyd items path'},
            SpiderConfig('spider name', 'spider project'),
            scrapyd,
        )

        job_id = helper.start_job({})

        self.assertEqual("XXX", job_id)

    def test_when_a_job_exists_then_it_should_report_its_status(self):
        scrapyd = mock.MagicMock(spec=Scrapyd)
        scrapyd.get_jobs.return_value = {
            '2f16646cfcaf11e1b0090800272a6d06': {
                'id': '2f16646cfcaf11e1b0090800272a6d06',
                'spider': 'spider3',
                'status': 'finished',
            },
            '78391cc0fcaf11e1b0090800272a6d06': {
                'id': '78391cc0fcaf11e1b0090800272a6d06',
                'project_name': 'spider1',
                'status': 'pending',
            },
        }

        helper = ScrapydJobHelper(
            {ScrapydJobHelper.SCRAPYD_ITEMS_PATH: 'scrapyd items path'},
            SpiderConfig('spider name', 'spider project'),
            scrapyd,
        )

        status = helper.report_on_job("2f16646cfcaf11e1b0090800272a6d06")

        self.assertEqual(ScrapydJobHelper.JobStatus.finished, status)

        scrapyd.get_jobs.assert_called_once_with(['spider project'], False)

    def test_when_a_job_is_unknown_then_it_should_retry(self):
        scrapyd = mock.MagicMock(spec=Scrapyd)
        scrapyd.get_jobs.side_effect = [
            {},
            {},
            {
                '2f16646cfcaf11e1b0090800272a6d06': {
                    'id': '2f16646cfcaf11e1b0090800272a6d06',
                    'spider': 'spider3',
                    'status': 'finished',
                },
                '78391cc0fcaf11e1b0090800272a6d06': {
                    'id': '78391cc0fcaf11e1b0090800272a6d06',
                    'project_name': 'spider1',
                    'status': 'pending',
                },
            },
        ]

        helper = ScrapydJobHelper(
            {ScrapydJobHelper.SCRAPYD_ITEMS_PATH: 'scrapyd items path'},
            SpiderConfig('spider name', 'spider project'),
            scrapyd,
        )

        status = helper.report_on_job("2f16646cfcaf11e1b0090800272a6d06")

        self.assertEqual(ScrapydJobHelper.JobStatus.finished, status)

        scrapyd.get_jobs.assert_called_with(['spider project'], True)

    def test_when_a_job_is_unknown_consistently_then_it_should_consider_it_unknonw(
            self):
        scrapyd = mock.MagicMock(spec=Scrapyd)
        scrapyd.get_jobs.side_effect = [
            {},
            {
                '2f16646cfcaf11e1b0090800272a6d06': {
                    'id': '2f16646cfcaf11e1b0090800272a6d06',
                    'spider': 'spider3',
                    'status': 'finished',
                },
                '78391cc0fcaf11e1b0090800272a6d06': {
                    'id': '78391cc0fcaf11e1b0090800272a6d06',
                    'project_name': 'spider1',
                    'status': 'pending',
                },
            },
        ]

        helper = ScrapydJobHelper(
            {ScrapydJobHelper.SCRAPYD_ITEMS_PATH: 'scrapyd items path'},
            SpiderConfig('spider name', 'spider project'),
            scrapyd,
        )

        status = helper.report_on_job(
            "2f16646cfcaf11e1b0090800272a6d06", max_retries=0)

        self.assertEqual(ScrapydJobHelper.JobStatus.unknown, status)

        scrapyd.get_jobs.assert_called_once_with(['spider project'], False)
