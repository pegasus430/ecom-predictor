from flask import Flask, Response, request, render_template_string
from functools import wraps
from subprocess import check_output, STDOUT
import re

TEMPLATE_STRING = '''
    {% if error %}
        <p style="color:red">{{error}}</p>
    {% endif %}
    <form name="switch_branch" action="{{url_for('switch_branch')}}" method='POST'>
    <input type="text" name="branch"></input>
    <button type="submit">Switch</button>
    </form>
    <p>Current branch: {{current_branch}}</p>'
    '''

app = Flask(__name__)

def check_auth(username, password):
    return username == 'tester' and password == '/fO+oI7LfsA='

def authenticate():
    return Response(
    'Please enter credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/switch_branch', methods=['GET', 'POST'])
@requires_auth
def switch_branch():
    error = None

    # if method is POST, switch branch before rendering
    if request.method == 'POST':
        try:
            # fetch any new branches
            check_output(['sudo', '-u', 'ubuntu', 'git', 'fetch'])

            # checkout requested branch
            check_output(['sudo', '-u', 'ubuntu', 'git', 'checkout', '-f', request.form['branch']], \
                stderr=STDOUT)

            # pull any changes
            check_output(['sudo', '-u', 'ubuntu', 'git', 'pull'])

            # restart flask
            check_output(['sudo', 'service', 'flask-uwsgi', 'stop'])
            check_output(['sudo', 'service', 'flask-uwsgi', 'start'])

        except Exception, e:
            error = e.output

    # get status
    status = check_output(['git', 'status'])

    # get current branch
    current_branch = re.search('On branch (.*)', status).group(1)

    return render_template_string(TEMPLATE_STRING, \
        current_branch = current_branch, \
        error = error)

if __name__ == '__main__':
    app.run('0.0.0.0', port=8080)
