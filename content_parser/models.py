from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class ImportTask(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.String(32), index=True, nullable=False)
    log_path = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    ended_at = db.Column(db.DateTime, nullable=True)
    import_config = db.Column(db.Text)
    is_finished = db.Column(db.Boolean, default=False)
    task_state = db.Column(db.String(16), nullable=True)
    progress_state = db.Column(db.String(100), nullable=True)
    error = db.Column(db.Text, nullable=True)
    stacktrace = db.Column(db.Text, nullable=True)

    def __init__(self, task_id, import_config, **kwargs):
        self.task_id = task_id
        self.import_config = import_config
        for k, v in kwargs.iteritems():
            self.__setattr__(k, v)
