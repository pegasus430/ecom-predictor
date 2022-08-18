from app import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    name = db.Column(db.String(256), nullable=False)
    password = db.Column(db.String(256), nullable=False)

    def __init__(self, name, password):
        self.name = name
        self.password = password

db.create_all()

if not User.query.all():
    admin = User(name='admin', password='p38YuqNm(t58X8PaV45%')

    db.session.add(admin)
    db.session.commit()
