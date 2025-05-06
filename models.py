from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# ─── USERS DB ──────────────────────────────────────
class User(db.Model, UserMixin):
    __bind_key__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=True)

# ─── BUDGET DB ─────────────────────────────────────
class Transaction(db.Model):
    __bind_key__ = 'budget'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)

class Budget(db.Model):
    __bind_key__ = 'budget'
    id = db.Column(db.Integer, primary_key=True)
    total = db.Column(db.Float, default=0)
    user_id = db.Column(db.Integer, unique=True, nullable=False)

class Category(db.Model):
    __bind_key__ = 'budget'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    __table_args__ = (
        db.UniqueConstraint('name', 'kind', 'user_id', name='_name_kind_user_uc'),
    )
