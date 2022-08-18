import os

import flask.ext.login as flask_login


CWD = os.path.dirname(os.path.abspath(__file__))


def load_credentials(fname='credentials.txt'):
    with open(os.path.join(CWD, fname), 'r') as fh:
        return [l.strip().split(';') for l in fh.readlines() if l.strip()]


class User(flask_login.UserMixin):
    pass


def user_loader(username):
    if username not in [c[0] for c in load_credentials()]:
        return
    user = User()
    user.id = username
    return user


def request_loader(request):
    username = request.form.get('username')
    if username not in [c[0] for c in load_credentials()]:
        return
    user = User()
    user.id = username

    for cred_login, cred_password in load_credentials():
        if cred_login.strip() == request.form.get('username', None):
            if cred_password.strip() == request.form.get('password', None):
                user.is_authenticated = True

    return user