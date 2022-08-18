import flask_login

from app import app
from flask import Response

login_manager = flask_login.LoginManager()


def get_user():
    return app.config['CSRF_SESSION_KEY'][20:30]


def get_password():
    return app.config['CSRF_SESSION_KEY'][30:40]


def get_api_key():
    return app.config['CSRF_SESSION_KEY'][:20]


@login_manager.request_loader
def check_api_key(request):
    api_key = request.headers.get(app.config['API_KEY_HEADER'])

    if api_key == get_api_key():
        return flask_login.UserMixin()

    auth = request.authorization

    if auth and auth.username == get_user() and auth.password == get_password():
            return flask_login.UserMixin()

    return None


@login_manager.unauthorized_handler
def unauthorized():
    return Response('Login Failed', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

login_manager.init_app(app)
