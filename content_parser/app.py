import os
import config
import json

from crontab import CronTab
from celery.states import READY_STATES
from flask import Flask, Response, render_template, request, send_file, jsonify, redirect, url_for
from datetime import datetime
from cron_config import CronConfig

from parsers import load_parsers
from parsers import Parser
from tasks import import_products
from models import db
from models import ImportTask

app = Flask(__name__)
app.config.from_object('config')
db.init_app(app)
with app.app_context():
    db.create_all()

IMPORT_TYPES = (
    (Parser.IMPORT_TYPE_PRODUCTS_AND_IMAGES, 'Content & Images'),
    (Parser.IMPORT_TYPE_PRODUCTS, 'Content'),
    (Parser.IMPORT_TYPE_IMAGES, 'Images')
)


@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'GET':
        cron_config = CronConfig()
        companies = cron_config.crons().keys()
        company_config = cron_config.get(request.args.get('company'))
        available_parsers = load_parsers(app.config['PARSERS_PACKAGE']).keys()

        return render_template(
            'index.html',
            companies=companies,
            company_config=company_config,
            import_types=IMPORT_TYPES,
            parsers=available_parsers
        )
    parser_name = request.form['parser']
    import_config = {
        'sftp': {
            'server': request.form['sftp_server'],
            'user': request.form['sftp_user'],
            'password': request.form['sftp_password'],
            'dir': request.form['sftp_dir']
        },
        'endpoint': {
            'url': request.form['endpoint_url'],
            'username': request.form['endpoint_username'],
            'password': request.form['endpoint_password'],
            'customer': request.form['endpoint_customer']
        },
        'import_type': request.form.get('import_type', Parser.IMPORT_TYPE_PRODUCTS_AND_IMAGES)
    }

    filename = None
    sftp_file = request.files.get('sftp_file')
    if sftp_file:
        filename = os.path.join(config.RESOURCES_DIR, sftp_file.filename)
        sftp_file.save(filename)
        os.chmod(filename, 0o777)  # make it accessible to all to rewrite it without issues

    celery_task = import_products.delay(parser_name, import_config, filename)
    task = ImportTask(task_id=celery_task.id, import_config=json.dumps(import_config))

    db.session.add(task)
    db.session.commit()

    return redirect(url_for('task_list'))


@app.route('/task_list', methods=['GET'])
def task_list():
    page_size = 20

    def _update_not_finished_tasks(_tasks):
        for _task in _tasks:
            task_instance = import_products.AsyncResult(_task.task_id)
            if task_instance.state in READY_STATES:
                _task.is_finished = True
                _task.ended_at = getattr(task_instance, '_cache', {}).get('date_done', datetime.now())
                _task.log_path = task_instance.result.get('log')
                _task.progress_state = 'Finished'
            else:
                if task_instance.result:
                    _task.progress_state = task_instance.result.get('progress')
            if task_instance.result and 'error' in task_instance.result:
                _task.error = task_instance.result.get('error')
                _task.stacktrace = task_instance.result.get('stacktrace')
                _task.progress_state = 'Error'
            _task.task_state = task_instance.state
        db.session.commit()

    not_finished_tasks = ImportTask.query.filter_by(is_finished=False)
    _update_not_finished_tasks(not_finished_tasks)

    page = request.args.get('page') or 1
    page = int(page)
    tasks_total = db.session.query(ImportTask.id).count()
    offset = page_size * (page - 1)
    limit = page_size * page
    tasks = ImportTask.query.order_by(ImportTask.created_at.desc()).slice(offset, limit)
    return render_template(
        'task_list.html',
        tasks=tasks,
        tasks_total=tasks_total,
        page_size=page_size,
        current_page=page
    )


@app.route('/task_log/<task_id>', methods=['GET'])
def task_log(task_id):
    task = ImportTask.query.filter_by(task_id=task_id).first()
    return send_file(
        task.log_path,
        mimetype='text/plain',
        as_attachment=True,
        attachment_filename=os.path.basename(task.log_path)
    )


@app.route('/import_task_config/<task_id>', methods=['GET'])
def import_task_config(task_id):
    task = ImportTask.query.filter_by(task_id=task_id).first()
    conf = task.import_config
    return Response(conf, mimetype='text/json')


@app.route('/crons')
def crons():
    crons = CronConfig().crons()
    crontab = CronTab(user=True)

    for company, cron in crons.iteritems():
        job = list(crontab.find_comment(company))
        if job:
            # remove old job
            crontab.remove(job[0])

        if cron.get('enabled'):
            # add new job if enabled
            job = crontab.new(
                'python '
                '{script} '
                '{company} '
                '-c {config} '
                '-l {log} '
                '>/dev/null 2>&1'.format(
                    script=os.path.join(app.config['BASE_DIR'], 'cron.py'),
                    company=company,
                    config=os.path.join(app.config['BASE_DIR'], 'cron_config.json'),
                    log=os.path.join(app.config['RESOURCES_DIR'], '{}_import.log'.format(company))
                ),
                comment=company
            )
            job.setall(cron['schedule'])
    crontab.write_to_user()
    return jsonify(crons)
