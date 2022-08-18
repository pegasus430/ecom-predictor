import os.path
import json
import logging
import functools
import sqlite3

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.events import (NewRequest, subscriber, ApplicationCreated)


LOG = logging.getLogger('url_service')


HERE = os.path.dirname(os.path.abspath(__file__))
DB_FN = 'url_service.sqlite'
SCHEMA_FN = 'schema.sql'


@view_config(route_name='queued_url', renderer='json',
             request_method='GET')
def queued_url(request):
    try:
        # Parse input.
        block = 'true' == request.params.get('block', 'true').lower()
        limit = int(request.params.get('limit', '100'))
        if limit < 1:
            raise ValueError("Limit cannot be negative.")
    except ValueError:
        msg = "Limit must be a natural number, not '%s'." \
            % request.params['limit']
        LOG.info("Client error: %s", msg)
        response = Response(body=json.dumps(msg), status=404,
                            content_type='application/json')
    else:
        LOG.info("Returning up to %d queued URLs while %sblocking.", limit,
                 '' if block else 'not ')

        db = request.db
        if block:
            db.isolation_level = 'EXCLUSIVE'

        cur = db.execute(
            """SELECT url, url_id, imported_data_id, category_id, 42 AS bid
            FROM queued_url ORDER BY id LIMIT %d""" % limit)
        response = [{k: str(v) for k, v in row}
                    for row in map(
                        functools.partial(zip, ['url', 'id',
                                                'imported_data_id',
                                                'category_id', 'bid']),
                        cur.fetchall())]
    return response


@view_config(route_name='save_parsed_from_text',
             request_method='POST')
def save_parsed_from_text(request):
    LOG.info("Saving page for URL '%s'.", request.POST.get('url'))

    try:
        request.db.execute(
            """INSERT
               INTO raw_pages (url, url_id, imported_data_id, category_id,
                    text, request_debug_info)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [request.POST['url'],
             int(request.POST['id']),
             int(request.POST['imported_data_id']),
             int(request.POST['category_id']),
             request.POST['text'],
             request.POST['info']])
        request.db.commit()
    except KeyError as e:
        msg = "Field '%s' missing from data." % e.args
        LOG.info("Client error: %s", msg)
        response = Response(body=json.dumps(msg), status=404,
                            content_type='application/json')
    except ValueError as e:
        msg = e.message
        LOG.info("Client error: %s", msg)
        response = Response(body=json.dumps(msg), status=404,
                            content_type='application/json')
    else:
        response = Response()

    return response


@view_config(route_name='url_load_failed',
             request_method='POST')
def url_load_failed(request):
    LOG.info("Failed to retrieve page for URL id %s.", request.POST.get('id'))

    try:
        request.db.execute(
            """INSERT INTO load_failure (url_id, http_code, error_string)
               VALUES (?, ?, ?)""",
            [int(request.POST['id']),
             int(request.POST['http_code']),
             request.POST['error_string']])
        request.db.commit()
    except KeyError as e:
        msg = "Field '%s' missing from data." % e.args
        LOG.info("Client error: %s", msg)
        response = Response(body=json.dumps(msg), status=404,
                            content_type='application/json')
    except ValueError as e:
        msg = e.message
        LOG.info("Client error: %s", msg)
        response = Response(body=json.dumps(msg), status=404,
                            content_type='application/json')
    else:
        response = Response()

    return response


## subscribers

@subscriber(ApplicationCreated)
def application_created_subscriber(event):
    """Create the schema if it doesn't exist."""
    LOG.info('Initializing database...')
    with open(os.path.join(HERE, SCHEMA_FN)) as f:
        stmt = f.read()

    db = sqlite3.connect(os.path.join(HERE, DB_FN))
    db.executescript(stmt)


@subscriber(NewRequest)
def open_db_session(event):
    """Open a DB session (connection) for every request."""
    request = event.request
    request.db = sqlite3.connect(os.path.join(HERE, DB_FN))
    request.add_finished_callback(close_db_connection)


def close_db_connection(request):
    """Close the DB session (connection) after every request."""
    request.db.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    config = Configurator()
    config.add_view(queued_url, route_name='queued_url')
    config.add_route('queued_url', '/get_queued_urls/')
    config.add_route('save_parsed_from_text', '/save_parsed_from_text/')
    config.add_route('url_load_failed', '/url_load_failed/')
    config.scan('.')
    app = config.make_wsgi_app()

    server = make_server('0.0.0.0', 8080, app)
    server.serve_forever()
