import os
import sys
import Auditor
import traceback
import logging
from datetime import datetime

from flask import request, render_template, send_file, jsonify

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..'))

from special_crawler.crawler_service import app

app.template_folder = os.path.join(CWD, 'templates')

# configure root logger
logger = logging.getLogger('mediaaudit')
fh = logging.StreamHandler()
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(fh)


@app.route("/run")
def run():
    return render_template(
        'run.html',
        data=[{'name': 'Kohls'}, {'name': 'Macys'}, {'name': 'JCPenny'}]
    )


@app.route("/runaction", methods=['GET', 'POST'])
def runaction():
    site_name = request.form.get('site_select')
    excel_file = request.files.get('fileupload')

    output_file = '/var/tmp/AuditResults_{}.xlsx'.format(datetime.now().strftime('%Y%m%d%H%M%S'))

    try:
        Auditor.initialize(site_name, excel_file, output_file)

        if os.path.isfile(output_file):
            return send_file(output_file, as_attachment=True, attachment_filename='AuditResults.xlsx')
        else:
            raise Exception('{} does not exist'.format(output_file))
    except Exception as e:
        logger.error(traceback.format_exc())

        return jsonify({
            'error': True,
            'message': str(e)
        })


@app.route("/fileconvert")
def fileconvert():
    return render_template('fileconvert.html')


@app.route("/runfileconvertaction", methods=['GET', 'POST'])
def runfileconvertaction():
    excel_file = request.files.get('fileupload')

    output_file = '/var/tmp/ConvertedResults_{}.xlsx'.format(datetime.now().strftime('%Y%m%d%H%M%S'))

    try:
        Auditor.convert(excel_file, output_file)

        if os.path.isfile(output_file):
            return send_file(output_file, as_attachment=True, attachment_filename='ConvertedResults.xlsx')
        else:
            raise Exception('{} does not exist'.format(output_file))
    except Exception as e:
        logger.error(traceback.format_exc())

        return jsonify({
            'error': True,
            'message': str(e)
        })


if __name__ == '__main__':
    app.run('0.0.0.0', port=8080, threaded=True)
