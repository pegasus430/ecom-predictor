import boto
import socket
import traceback

from flask import Flask, abort, request, make_response, jsonify
from spider.retail_link import WalmartRetailCrawler, WalmartRetailCrawlerException

app = Flask(__name__)


@app.route('/get_file/')
def get_file():
    print 'R', request

    user = request.args.get('user')
    print 'USER', user
    password = request.args.get('password')
    print 'PASSWORD', password

    if not user and not password:
        return abort(400)

    name_report = request.args.get('name_report') or ''
    print 'NR', name_report

    res = donwload()

    if isinstance(res, tuple):
        return res

    fp = res

    file = open(fp, 'r')
    response = make_response(file.read())
    file.close()

    response.headers['Content-Disposition'] = 'attachment; filename="%s"' % fp.split('/')[-1]
    # TODO: is this still the correct content-type?
    response.headers['Content-Type'] = 'application/vnd.ms-excel'
    return response


@app.route('/download/')
def donwload():
    auth_test = False

    try:
        user = request.args.get('user') or ''
        password = request.args.get('password') or ''
        name_report = request.args.get('name_report') or ''

        if not name_report:
            auth_test = True

        crawler = WalmartRetailCrawler()
        crawler.do_login(user, password)

        file_path = None

        if not auth_test:
            file_path = crawler.get_report(name_report)

        return file_path if not auth_test else (jsonify({'message': 'success'}), 200)

    except WalmartRetailCrawlerException, e:
        print 'EXCEPTION', e

        if not auth_test:
            send_email_to_support(e, request.args.get('email'))

        return jsonify({
            'error': str(e),
            'responses': getattr(e, 'responses', None)
        }), 400

    except Exception, e:
        print 'UNKNOWN EXCEPTION', traceback.format_exc()

        if not auth_test:
            send_email_to_support(e, request.args.get('email'))

        return jsonify({
            'error': str(e),
            'responses': getattr(e, 'responses', None)
        }), 400


def send_email_to_support(error, address=None):
    sender = 'noreply@contentanalyticsinc.com'
    receivers = [address if address else 'support@contentanalyticsinc.com']

    print 'Sending email to {}'.format(receivers)

    server = request.args.get('server')
    if not server:
        try:
            server = socket.gethostbyaddr(request.remote_addr)[0]
        except:
            server = 'Unknown server'

    subject = 'Retail Link Sales Import Failed: {}'.format(server)

    message = 'Failed to fetch Retail Link sales data.\nError:\n{error}\nResponses:\n{responses}'.format(
        error=error,
        responses=getattr(error, 'responses', None)
    )

    try:
        ses = boto.connect_ses()
        ses.send_email(source=sender,
                       subject=subject,
                       body=message,
                       to_addresses=receivers)
    except Exception as e:
        print 'Can not send email: {}'.format(e)


if __name__ == '__main__':
    app.run('0.0.0.0', threaded=True, port=8080)
