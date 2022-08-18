from functools import partial

from pyramid import testing
import pyramid.httpexceptions as exc
from pyspecs import given, when, then, the, finish
import mock

from web_runner import views


with given.a_configuration_with_one_spider:
    settings = {
        'spider._names': 'spider_cfg',
        'spider._scrapyd.base_url': 'http://localhost:6800/',
        'spider._result.base_url': 'http://localhost:8000/',
        'spider.spider_cfg.resource': 'spider_resource',
        'spider.spider_cfg.spider_name': 'spider_name',
        'spider.spider_cfg.project_name': 'spider_project_name',

        'db_filename': ":memory:",
    }

    request = testing.DummyRequest(
        path="/spider_resource/",
        post=dict(site='example', searchterms_str='a search terms'),
        remote_addr="127.0.0.1",
    )

    with testing.testConfig(request=request, settings=settings) as config:
        # Mock ScrapydJobHelper to isolate the test.
        with mock.patch('web_runner.views.ScrapydJobHelper') \
                as ScrapydJobHelperMock:
            with mock.patch('web_runner.db.DbInterface') as DbMock:
                helper_mock = ScrapydJobHelperMock.return_value
                helper_mock.start_job.return_value = "XXX"

                # Pyramid testing doesn't configure resources.
                request.route_path = mock.MagicMock()

                with when.starting_a_spider:
                    with then.it_should_redirect_to_pending_state:
                        the(
                            partial(views.spider_start_view, request)
                        ).should.raise_an(exc.HTTPFound)


with given.a_configuration_with_one_command_and_spider:
    settings = {
        'command._names': "cmd_cfg",
        'command.cmd_cfg.cmd': "command line '{spider 0}'",
        'command.cmd_cfg.resource': 'command_resource',
        'command.cmd_cfg.content_type': 'application/x-ldjson',
        'command.cmd_cfg.crawl.0.spider_config_name': 'spider_cfg',

        'spider._names': 'spider_cfg',
        'spider._scrapyd.base_url': 'http://localhost:6800/',
        'spider._result.base_url': 'http://localhost:8000/',
        'spider.spider_cfg.resource': 'spider_resource',
        'spider.spider_cfg.spider_name': 'spider_name',
        'spider.spider_cfg.project_name': 'spider_project_name',

        'db_filename': ":memory:",
    }

    request = testing.DummyRequest(
        path="/command_resource/",
        post=dict(site='example', searchterms_str='a search terms'),
        remote_addr="127.0.0.1",
    )

    with testing.testConfig(request=request, settings=settings):
        # Mock ScrapydJobHelper to isolate the test.
        with mock.patch('web_runner.views.ScrapydJobHelper') \
                as ScrapydJobHelperMock:
            with mock.patch('web_runner.db.DbInterface') as DbMock:
                helper_mock = ScrapydJobHelperMock.return_value
                helper_mock.start_job.return_value = "XXX"

                # Pyramid testing doesn't configure resources.
                request.route_path = mock.MagicMock()

                with when.starting_a_command:
                    cmd_request = partial(views.command_start_view, request)

                    with then.it_should_redirect_to_pending_state:
                        the(cmd_request).should.raise_an(exc.HTTPFound)


if __name__ == '__main__':
    finish()
