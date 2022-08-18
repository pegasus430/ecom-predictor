import flask_login

from app import app
from models import User
from flask import Response

login_manager = flask_login.LoginManager()


@login_manager.request_loader
def check_user_password(request):
    auth = request.authorization

    if auth:
        user = User.query.filter_by(name=auth.username, password=auth.password).first()
        if user:
            return user

    return None


@login_manager.unauthorized_handler
def unauthorized():

    return Response('Login Failed', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})


login_manager.init_app(app)
