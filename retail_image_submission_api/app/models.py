from app import db
from datetime import datetime


class Submission(db.Model):

    STATE_RECEIVED = 'received'
    STATE_PROCESSING = 'processing'
    STATE_READY = 'ready'
    STATE_ERROR = 'error'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    feed_id = db.Column(db.String(32), index=True, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True, nullable=False)
    user = db.relationship('User', backref=db.backref('submissions', lazy='dynamic'))

    state = db.Column(db.Enum(STATE_RECEIVED, STATE_PROCESSING, STATE_READY, STATE_ERROR, name='states'),
                      nullable=False, default=STATE_RECEIVED)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    request = db.Column(db.Text, nullable=False)
    message = db.Column(db.Text, nullable=True)

    def __init__(self, request, feed_id, user, **kwargs):
        self.request = request
        self.feed_id = feed_id
        self.user = user

        for k, v in kwargs.iteritems():
            self.__setattr__(k, v)


class SubmissionResults(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), index=True, nullable=False)
    submission = db.relationship('Submission', backref=db.backref('results', uselist=False))

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    name = db.Column(db.String(1024), nullable=False)

    def __init__(self, name):
        self.name = name


db.create_all()
