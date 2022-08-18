import json

from app import db
from datetime import datetime

from sqlalchemy.ext.hybrid import hybrid_property


class Submission(db.Model):

    STATE_RECEIVED = 'received'
    STATE_PROCESSING = 'processing'
    STATE_READY = 'ready'
    STATE_ERROR = 'error'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    feed_id = db.Column(db.String(32), index=True, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True, nullable=False)
    user = db.relationship('User', backref=db.backref('submissions', lazy='dynamic'))

    sandbox = db.Column(db.Boolean, nullable=False, default=False)

    state = db.Column(db.Enum(STATE_RECEIVED, STATE_PROCESSING, STATE_READY, STATE_ERROR, name='states'),
                      nullable=False, default=STATE_RECEIVED)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    request = db.Column(db.Text, nullable=False)
    message = db.Column(db.Text, nullable=True)

    async_check = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, request, feed_id, sandbox=False, **kwargs):
        self.request = request
        self.feed_id = feed_id
        self.sandbox = sandbox

        for k, v in kwargs.iteritems():
            self.__setattr__(k, v)


class SubmissionResults(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), index=True, nullable=False)
    submission = db.relationship('Submission', backref=db.backref('results', uselist=False))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    url = db.Column(db.String(1024), nullable=False)

    def __init__(self, url):
        self.url = url


class SubmissionScreenshots(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), index=True, nullable=False)
    submission = db.relationship('Submission', backref=db.backref('screenshots', uselist=False))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    url = db.Column(db.String(1024), nullable=False)

    def __init__(self, url):
        self.url = url


class SubmissionData(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), index=True, nullable=False)
    submission = db.relationship('Submission', backref=db.backref('data', uselist=False))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    _data = db.Column(db.Text, nullable=False)

    @hybrid_property
    def data(self):
        return json.loads(self._data)

    @data.setter
    def data(self, value):
        self._data = json.dumps(value)

    def __init__(self, data):
        self.data = data

db.create_all()
