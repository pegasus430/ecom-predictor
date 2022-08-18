import flask_login
from app import app
from models import User

login_manager = flask_login.LoginManager()


@login_manager.request_loader
def check_api_key(request):
    api_key = request.headers.get(app.config['API_KEY_HEADER'])

    if api_key:
        user = User.query.filter_by(api_key=api_key).first()
        if user:
            return user

    return None

login_manager.init_app(app)
