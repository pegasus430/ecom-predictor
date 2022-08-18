import collections
from itertools import count

import pyramid.httpexceptions as exc


SpiderConfig = collections.namedtuple('SpiderConfig',
                                      ['spider_name', 'project_name'])


CommandConfig = collections.namedtuple(
    'CommandConfig',
    ['name', 'cmd', 'content_type', 'spider_configs', 'spider_params']
)


def find_spider_config_from_path(settings, path):
    path = path.strip('/')

    for name in settings['spider._names'].split():
        prefix = 'spider.{}.'.format(name)

        resource = settings[prefix + 'resource']
        if resource.strip('/') == path:
            return find_spider_config_from_name(settings, name)
    raise exc.HTTPNotFound("Resource '%s' is unknown." % path)


def find_spider_config_from_name(settings, name):
    prefix = 'spider.{}.'.format(name)

    try:
        return SpiderConfig(
            settings[prefix + 'spider_name'],
            settings[prefix + 'project_name'],
        )
    except KeyError:
        raise exc.HTTPNotFound("Spider with name '%s' not found." % name)


def find_command_config_from_path(settings, path):
    path = path.strip('/')

    for name in settings.get('command._names', '').split():
        prefix = 'command.{}.'.format(name)

        resource = settings[prefix + 'resource']
        if resource.strip('/') == path:
            return find_command_config_from_name(settings, name)

    raise exc.HTTPNotFound("Command for '%s' not found." % path)


def find_command_config_from_name(settings, name):
    prefix = 'command.{}.'.format(name)

    crawl_configs, crawl_params = list(zip(
        *find_command_crawls(settings, prefix + 'crawl.')))
    assert len(crawl_configs) == len(crawl_params)

    return CommandConfig(
        name,
        settings[prefix + 'cmd'],
        settings[prefix + 'content_type'],
        crawl_configs,
        crawl_params,
    )


def find_command_crawls(settings, prefix):
    try:
        for i in count():
            spider_config_name_key = prefix + str(i) + '.spider_config_name'
            spider_config_name = settings[spider_config_name_key]

            cfg = find_spider_config_from_name(
                settings, spider_config_name)
            if cfg is None:
                raise Exception(
                    "Spider configuration name '%s' is not defined."
                    % spider_config_name)

            try:
                spider_params_name = prefix + str(i) + '.spider_params'
                params_list = settings[spider_params_name].split()
                params = dict(raw_param.split('=', 1)
                              for raw_param in params_list)
            except KeyError:
                params = {}  # No parameters defined.

            yield cfg, params
    except KeyError:
        pass  # No more crawlers.


def render_spider_config(spider_template_config, params, *more_params):
    """Renders the spider config from the given templates and parameters.

    :param spider_template_config: A config templates.
    :type spider_template_config: SpiderConfig
    :param params: A dict with the values for the template.
    :type params: dict
    :param more_params: Dicts to override parameters for the template.
    :type more_params: dict
    :returns: A rendered SpiderConfigs.
    """
    merged_params = dict(params)
    for p in more_params:
        merged_params.update(p)

    return SpiderConfig(
        spider_template_config.spider_name.format(**merged_params),
        spider_template_config.project_name.format(**merged_params)
    )
