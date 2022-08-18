import re
import xml
import requests
import pg_parser
import kwikee_parser
from flask import request, jsonify

from app import app

MC_API = '/'

ERR_MESSAGE = (
    'Please specify the url of an %s file to parse e.g. '
    'http://matt-test.contentanalyticsinc.com:8888/parse?url=http://<server>/<path-to-file>/filename.%s'
)


def _wrap(message):
    return jsonify({'message': message})


@app.route('/parse', methods=['GET'])
def parse():
    url = request.args.get('url')

    if not url:
        return _wrap(ERR_MESSAGE % (('xml/xls(x)',)*2)), 400

    filename = url.split('/')[-1]

    template = request.args.get('template')

    if template == 'kwikee':
        if not re.search('\.xlsx?$', filename):
            return _wrap(ERR_MESSAGE % (('xls(x)',)*2)), 400
    else:
        if not re.search('\.xml$', filename):
            return _wrap(ERR_MESSAGE % (('xml',)*2)), 400

    try:
        r = requests.get(url)
    except:
        return _wrap('There was an error connecting to ' + url), 400

    if not r.status_code == 200:
        return _wrap('Not found: ' + url), 404

    content = r.content

    if template == 'kwikee':
        parser = kwikee_parser
    else:
        parser = pg_parser

    try:
        parser.setup_parse(content, MC_API)
    except (ValueError, xml.etree.ElementTree.ParseError) as e:
        return _wrap('Error parsing %s with %s template parser: %s' % (filename, template, e.message)), 400
    except Exception as e:
        print e
        return _wrap('An error occurred'), 400

    return _wrap(filename + ' is being parsed and the result will be sent to ' + MC_API)

if __name__ == '__main__':
    app.run('0.0.0.0', debug=True, port=8888)
