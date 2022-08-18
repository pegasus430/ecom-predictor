from functools import partial

from pyspecs import given, when, then, the, finish
import pyramid.httpexceptions as exc

from web_runner.config_util import find_spider_config_from_path, SpiderConfig
from web_runner.config_util import find_command_config_from_path, CommandConfig


with given.a_configuration_of_a_spider:
    settings = {
        'spider._names': 'spider_cfg',

        'spider._scrapyd.base_url': 'http://localhost:6800/',
        'spider._result.base_url': 'http://localhost:8000/',

        'spider.spider_cfg.resource': 'spider_resource',
        'spider.spider_cfg.spider_name': 'spider_name',
        'spider.spider_cfg.project_name': 'spider_project_name',
    }

    with when.searching_for_that_resource:
        config = find_spider_config_from_path(settings, '/spider_resource/')

        with then.the_configuration_should_be_found:
            the(config).should.equal(
                SpiderConfig('spider_name', 'spider_project_name'))

    with when.searching_for_an_unexistant_resource:
        config = partial(
            find_command_config_from_path, settings, '/unexistant/')
        config.__name__ = "find_command_config_from_path"

        with then.it_should_raise_not_found:
            the(config).should.raise_an(exc.HTTPNotFound)


with given.a_configuration_of_a_command_with_one_spider:
    settings = {
        'spider._names': 'test_spider',
        'spider.test_spider.resource': '/spider/resource',
        'spider.test_spider.spider_name': 'spider name',
        'spider.test_spider.project_name': 'spider project',

        'command._names': 'tst',
        'command.tst.cmd': 'echo {key1}',
        'command.tst.resource': '/tst-resource',
        'command.tst.content_type': 'text/plain',
        'command.tst.crawl.0.spider_config_name': 'test_spider',
    }

    with when.searching_for_that_resource:
        config = find_command_config_from_path(settings, '/tst-resource/')

        with then.the_configuration_should_be_found:
            the(config).should.equal(CommandConfig(
                'tst',
                'echo {key1}',
                'text/plain',
                (SpiderConfig('spider name', 'spider project'),),
                ({},),
            ))

    with when.searching_for_an_unexistant_resource:
        config = partial(
            find_command_config_from_path, settings, '/unexistant/')
        config.__name__ = "find_command_config_from_path"

        with then.it_should_raise_not_found:
            the(config).should.raise_an(exc.HTTPNotFound)

with given.a_configuration_of_a_command_with_two_spiders:
    settings = {
        'spider._names': 'test_spider',
        'spider.test_spider.resource': '/spider/resource',
        'spider.test_spider.spider_name': 'spider name',
        'spider.test_spider.project_name': 'spider project',

        'command._names': 'tst',
        'command.tst.cmd': 'echo {key1}',
        'command.tst.resource': '/tst-resource',
        'command.tst.content_type': 'text/plain',
        'command.tst.crawl.0.spider_config_name': 'test_spider',
        'command.tst.crawl.1.spider_config_name': 'test_spider',
        'command.tst.crawl.1.spider_params': 'param1=value1 param2=value2',
    }

    with when.searching_for_that_resource:
        config = find_command_config_from_path(settings, '/tst-resource/')

        with then.the_configuration_should_be_found:
            the(config).should.equal(CommandConfig(
                'tst',
                'echo {key1}',
                'text/plain',
                (
                    SpiderConfig('spider name', 'spider project'),
                    SpiderConfig('spider name', 'spider project'),
                ),
                (
                    {},
                    {'param1': 'value1', 'param2': 'value2'},
                ),
            ))

    with when.searching_for_an_unexistant_resource:
        config = partial(
            find_command_config_from_path, settings, '/unexistant/')
        config.__name__ = "find_command_config_from_path"

        with then.it_should_raise_not_found:
            the(config).should.raise_an(exc.HTTPNotFound)


if __name__ == '__main__':
    finish()
