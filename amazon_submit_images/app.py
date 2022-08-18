# pip install flask-login
# pip install flask

import os
import time
import datetime
import sys
import string
import random
import tempfile
import json
import uuid

from flask import (Flask, request, flash, url_for, redirect, render_template,
                   session, send_file, jsonify)

import flask.ext.login as flask_login
from auth import user_loader, User, load_credentials

app = Flask(__name__)
CWD = os.path.dirname(os.path.abspath(__file__))

app.secret_key = 'F12Zr47j\3yX R~X@H!jmM]Lwf/,?KTSn  SKDk34k8**W$7SDfsdhSD4SDfggazsd'

CHECK_CREDENTIALS = False

login_manager = flask_login.LoginManager()
login_manager.user_callback = user_loader
login_manager.init_app(app)


def get_screenshots_bucket_path(random_id, bucket='vendor-central-submissions'):
    remote_arch_fname = datetime.datetime.now().strftime('%Y/%m/%d' + '/%s.zip' % random_id)
    return bucket + '/' + remote_arch_fname


def upload_file_to_our_server(file):
    fname = file.filename.replace('/', '')
    while fname.startswith('.'):
        fname = fname[1:]
    fname2 = ''
    for c in fname:
        if (c in string.ascii_lowercase or c in string.ascii_uppercase
                or c in string.digits or c in ('.', '_', '-')):
            fname2 += c
        else:
            fname2 += '-'
    fname = fname2
    if not os.path.exists(os.path.join(CWD, '_uploads')):
        os.makedirs(os.path.join(CWD, '_uploads'))
    tmp_local_file = os.path.join(CWD, '_uploads', fname)
    if os.path.exists(tmp_local_file):
        while os.path.exists(tmp_local_file):
            f_name, f_ext = tmp_local_file.rsplit('.', 1)
            f_name += str(random.randint(1, 9))
            tmp_local_file = f_name + '.' + f_ext
    file.save(tmp_local_file)
    return os.path.abspath(tmp_local_file)


def check_downloads_dir():
    """ Needed only for the first run """
    downloads_dir = os.path.join(CWD, '_downloads')

    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    else:
        for f in os.listdir(downloads_dir):
            os.remove(os.path.join(downloads_dir, f))

    return True


def run_spider_upload(username, password, local_file, task, do_submit, random_id):
    log_fname = tempfile.NamedTemporaryFile(delete=False)
    log_fname.close()
    log_fname = log_fname.name

    spiders_dir = os.path.join(CWD, '..', 'product-ranking',
                               'product_ranking', 'spiders')
    if not os.path.exists(spiders_dir):
        spiders_dir = '.'
    cmd = ('python {spiders_dir}/submit_amazon_images.py --username="{username}"'
           ' --password="{password}" --upload_file="{upload_file}" --logging_file="{log_file}" --task="{task}"'
           ' --submit={do_submit} --id="{random_id}"')
    cmd_run = cmd.format(username=username, password=password, upload_file=local_file,
                         log_file=log_fname, spiders_dir=spiders_dir, task=task, do_submit=do_submit,
                         random_id=random_id)
    print(cmd_run)
    os.system(cmd_run)
    return log_fname


def run_spider_upload_text(username, password, local_file, task, group, emails, do_submit, random_id):
    log_fname = tempfile.NamedTemporaryFile(delete=False)
    log_fname.close()
    log_fname = log_fname.name

    spiders_dir = os.path.join(CWD, '..', 'product-ranking',
                               'product_ranking', 'spiders')
    if not os.path.exists(spiders_dir):
        spiders_dir = '.'
    cmd = ('python {spiders_dir}/submit_amazon_images.py --username="{username}"'
           ' --password="{password}" --upload_file="{upload_file}" --logging_file="{log_file}"'
           ' --task="{task}" --group="{group}" --emails="{emails}" --submit={do_submit}'
           ' --id="{random_id}"')
    cmd_run = cmd.format(username=username, password=password, upload_file=local_file,
                         log_file=log_fname, spiders_dir=spiders_dir, task=task, group=group,
                         emails=emails, do_submit=do_submit, random_id=random_id)
    print(cmd_run)
    os.system(cmd_run)
    return log_fname


def run_spider_download(username, password, task, do_submit, random_id):
    log_fname = tempfile.NamedTemporaryFile(delete=False)
    log_fname.close()
    log_fname = log_fname.name
    spiders_dir = os.path.join(CWD, '..', 'product-ranking',
                               'product_ranking', 'spiders')
    if not os.path.exists(spiders_dir):
        spiders_dir = '.'
    cmd = ('python {spiders_dir}/submit_amazon_images.py --username={username}'
           ' --password={password} --logging_file={log_file} --task={task} --submit={do_submit}'
           ' --id="{random_id}"')

    cmd_run = cmd.format(username=username, password=password, log_file=log_fname,
                         spiders_dir=spiders_dir, task=task, random_id=random_id, do_submit=do_submit)
    print(cmd_run)
    os.system(cmd_run)
    return log_fname


def parse_log(log_fname):
    if not os.path.exists(log_fname):
        return False, 'log does not exist'
    is_success = True
    with open(log_fname, 'r') as fh:
        msgs = [json.loads(m.strip()) for m in fh.readlines() if m.strip()]
        if not msgs:
            is_success = False
        for msg in msgs:
            if msg.get('level', None) == 'error':
                is_success = False
        if msgs and msgs[-1].get('msg', None) != 'finished':
            is_success = False
    return is_success, msgs


def upload_view():
    username = request.form.get('username', None)
    password = request.form.get('password', None)
    file = request.files.get('file', None)
    task = request.form.get('task', None)
    group = request.form.get('group', None)
    emails = request.form.get('emails', None)
    do_submit = request.form.get('do_submit', False)

    random_id = uuid.uuid4()

    if not username:
        return 'Enter username'
    if not password:
        return 'Enter password'
    if task == 'image':
        if not file:
            return 'Select a file to upload'
        if not file.filename.lower().endswith('.zip'):
            return 'Please upload a zip file (ending with .zip)'
    elif task == 'text':
        if not file:
            return 'Select a file to upload'
        if not file.filename.lower().endswith('.xls'):
            return 'Please upload a file (ending with .xls)'

    time.sleep(1)  # against bruteforce attacks ;)
    for cred_login, cred_password in load_credentials():
        if username.strip() == cred_login.strip() or not CHECK_CREDENTIALS:
            if password.strip() == cred_password.strip() or not CHECK_CREDENTIALS:
                user = User()
                user.id = username
                flask_login.login_user(user)
                if task == 'image':
                    local_file = upload_file_to_our_server(file)
                    log_fname = run_spider_upload(username=username, password=password,
                        local_file=local_file, task=task, do_submit=do_submit, random_id=random_id)
                    success, messages = parse_log(log_fname)
                    return success, messages, task, random_id
                elif task == 'text':
                    local_file = upload_file_to_our_server(file)
                    log_fname = run_spider_upload_text(
                        username=username, password=password,
                        local_file=local_file, task=task, group=group,
                        emails=emails, do_submit=do_submit, random_id=random_id)
                    success, messages = parse_log(log_fname)
                    return success, messages, task, random_id
                elif task == 'genstatus':
                    log_fname = run_spider_download(username=username, password=password,
                        task=task, do_submit=do_submit, random_id=random_id)
                    success, messages = parse_log(log_fname)
                    return success, messages, task, random_id
                else:
                    if check_downloads_dir():
                        log_fname = run_spider_download(username=username, password=password,
                            task=task, do_submit=do_submit, random_id=random_id)
                        success, messages = parse_log(log_fname)
                        return success, messages, task, random_id

    return 'Invalid login or password'


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('upload.html')
    else:
        _msgs = upload_view()
        if isinstance(_msgs, (list, tuple)):
            success, messages, _task, random_id = _msgs
        else:
            return _msgs
        if not success:
            result_response = """
                <p>Status: <b>FAILED</b></p>
                <p>Screenshots: {screenshots}</p>
                <p>Log:</p>
                <p>{messages}</p>
            """.format(
                messages='<br/>'.join([m.get('msg') for m in messages]),
                screenshots=get_screenshots_bucket_path(random_id))
        else:
            result_response = """
                <p>Status: <b>FAILED</b></p>
                <p>Screenshots: {screenshots}</p>
                <p>Log:</p>
                <p>{messages}</p>
            """.format(
                messages='<br/>'.join([m.get('msg') for m in messages]),
                screenshots=get_screenshots_bucket_path(random_id))
        task = request.form.get('task', None)
        if (task != 'report') and (task != 'status'):
            return result_response
        elif not success :
            return result_response
        else:
            filepath = CWD+'/_downloads'
            filename = max([filepath +"/"+ f for f in os.listdir(filepath)], key=os.path.getctime)
            print filename
            if filename:
                return send_file(filename, mimetype='text/csv', as_attachment=True)

@app.route('/api', methods=['GET', 'POST'])
def api():
    if request.method == 'GET':
        return render_template('api.html')
    else:
        _msgs = upload_view()
        if isinstance(_msgs, (list, tuple)):
            success, messages, _task, random_id = _msgs
        else:
            return jsonify({'status': 'error', 'message': _msgs}), 400
        task = request.form.get('task', None)
        if not success:
            return jsonify({
                'status': 'error',
                'message': messages,
                'screenshots': get_screenshots_bucket_path(random_id)
            }), 400
        elif (task != 'report') and (task != 'status'):
            return jsonify({'status': 'success'})
        else:
            filepath = os.path.join(CWD, '_downloads')
            filename = max([filepath + "/" + f for f in os.listdir(filepath)], key=os.path.getctime)
            if filename:
                return send_file(filename, mimetype='text/csv', as_attachment=True)


if __name__ == '__main__':
    app.run(port=80, host='0.0.0.0')
