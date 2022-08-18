from app import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    name = db.Column(db.String(256), nullable=False)
    api_key = db.Column(db.String(256), nullable=False)

    def __init__(self, name, api_key):
        self.name = name
        self.api_key = api_key

db.create_all()

if not User.query.all():
    default_user = User(name='default', api_key='alo4yu8fj30ltb3r')

    db.session.add(default_user)
    db.session.commit()
