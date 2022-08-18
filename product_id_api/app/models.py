from app import db
from datetime import datetime


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    upc = db.Column(db.String(256), index=True, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=True)
    updated_by = db.Column(db.String(256), nullable=True)

    def __repr__(self):
        return self.upc


class Vsn(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(256), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True, nullable=False)
    product = db.relationship('Product', backref=db.backref('vsn', uselist=False))

    def __repr__(self):
        return self.value


class ToolId(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(256), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True, nullable=False)
    product = db.relationship('Product', backref=db.backref('toolid', uselist=False))

    def __repr__(self):
        return self.value


class Asin(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(256), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True, nullable=False)
    product = db.relationship('Product', backref=db.backref('asin', uselist=False))

    def __repr__(self):
        return self.value


class Tcin(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(256), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True, nullable=False)
    product = db.relationship('Product', backref=db.backref('tcin', uselist=False))

    def __repr__(self):
        return self.value


class Jet(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(256), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True, nullable=False)
    product = db.relationship('Product', backref=db.backref('jet', uselist=False))

    def __repr__(self):
        return self.value


class Tru(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(256), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), index=True, nullable=False)
    product = db.relationship('Product', backref=db.backref('tru', uselist=False))

    def __repr__(self):
        return self.value


db.create_all()
