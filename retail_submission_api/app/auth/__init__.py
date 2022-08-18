import flask_login

from app import app
from models import User
from flask import Response

login_manager = flask_login.LoginManager()


@login_manager.request_loader
def check_api_key(request):
    api_key = request.headers.get(app.config['API_KEY_HEADER'])

    if api_key:
        user = User.query.filter_by(api_key=api_key).first()
        if user:
            return user

    auth = request.authorization

    if auth:
        user = User.query.filter_by(name=auth.username, api_key=auth.password).first()
        if user:
            return user

    return None


@login_manager.unauthorized_handler
def unauthorized():
    return Response('Login Failed', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

login_manager.init_app(app)
