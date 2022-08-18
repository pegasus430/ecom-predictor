"""This REST service allows to run Scrapy spiders through
Scrapyd and to run commands over the resulting data.
"""
import logging
import os.path

from pyramid.config import Configurator
from pyramid.events import ApplicationCreated
from pyramid.events import subscriber

import web_runner.db

LOG = logging.getLogger(__name__)

@subscriber(ApplicationCreated)
def application_created_subscriber(event):
    """This method run when Pyramid startup

    This method mainly creates the internal DB structure"""
    settings = event.app.registry.settings
    db_filename = settings['db_filename']
    dbinterf = web_runner.db.DbInterface(db_filename, recreate=False)
    dbinterf.create_dbstructure()
    dbinterf.close()
    

def add_routes(settings, config):
    """Reads the configuration for commands and spiders and configures views to
    handle them.
    """
    for controller_type in ('command', 'spider'):
        names_key = '{}._names'.format(controller_type)
        for cfg_name in settings[names_key].split():
            resource_key = '{}.{}.resource'.format(controller_type, cfg_name)
            resource_path = os.path.normpath(settings[resource_key]) + '/'

            LOG.info("Configuring %s '%s' under '%s'.", controller_type,
                     cfg_name, resource_path)
            route_name = '{}-{}'.format(controller_type, cfg_name)
            config.add_route(route_name, resource_path)
            config.add_view(
                'web_runner.views.{}_start_view'.format(controller_type),
                route_name=route_name,
                request_method='POST',
            )


def main(global_config, **settings):
    """This function returns a Pyramid WSGI application."""
    config = Configurator(settings=settings)

    config.add_route("spider pending jobs",

                     '/crawl/project/{project}/spider/{spider}/job/{jobid}/')
    config.add_route("spider job results",
                     '/result/project/{project}/spider/{spider}/job/{jobid}/')
    config.add_route("spider history",
                     '/history/project/{project}/spider/{spider}/job/{jobid}/')

    config.add_route("command pending jobs", '/command/{name}/pending/{jobid}/')
    config.add_route("command job results", '/command/{name}/result/{jobid}/')
    config.add_route("command history", '/command/{name}/history/{jobid}/')
    config.add_route("status", '/status/')
    config.add_route("last request status", '/last_requests')
    config.add_route("request history", '/request/{requestid}/history/')

    add_routes(settings, config)

    config.scan()

    return config.make_wsgi_app()
