import os
import json
import uuid
import subprocess

LOG_FILE = None
CWD = ''


def set_cwd(path):
    global CWD
    CWD = path


def get_cwd():
    global CWD
    return CWD


def set_log_file(path):
    global LOG_FILE
    LOG_FILE = path


def get_log_file():
    global LOG_FILE
    return LOG_FILE


def logging_info(msg, level='INFO'):
    """ We're using JSON which is easier to parse """
    if not LOG_FILE:
        return

    with open(LOG_FILE, 'a') as fh:
        fh.write(json.dumps({'msg': msg, 'level': level})+'\n')

    print('CONVERTER LOGGING : [%s] %s' % (level, msg))


def get_result_file_name():
    if not os.path.exists(os.path.join(CWD, '_results')):
        os.makedirs(os.path.join(CWD, '_results'))
    filename = os.path.join(CWD, '_results', str(uuid.uuid4()))
    return filename


def write_to_file(content):
    filename = get_result_file_name()
    with open(filename, 'w') as result:
        result.write(content)

    return filename


def check_extension(filename, extensions):
    name, file_extension = os.path.splitext(filename)
    return file_extension in extensions


def do_convert(source_file):
    try:
        name, ext = os.path.splitext(source_file)
    except Exception as e:
        logging_info('CONVERSION ERROR (File not found): ' + str(e))
        return ''

    dst_file = name + '-cvt' + ext
    cmd_run = [
        '/usr/bin/unoconv',
        '-d',
        'spreadsheet',
        '--output',
        dst_file,
        '--format',
        'xls',
        source_file
    ]
    try:
        my_env = os.environ.copy()
        my_env["PATH"] = "/usr/bin:" + my_env["PATH"]
        subprocess.call(cmd_run, env=my_env)
    except Exception as e:
        logging_info('CONVERSION ERROR : ' + str(e))
    return dst_file


# xlrd does not parse PHP generated xls file, this function convert xls file to read xls file with xlrd.
def convert_xls_file(src_file):
    dst_file = ''
    repeat_cnt = 0

    # Run conversion command 3 times
    while True:
        dst_file = do_convert(src_file)
        repeat_cnt += 1
        if os.path.isfile(dst_file):
            break
        if repeat_cnt > 3 or dst_file == '':
            break
    return dst_file