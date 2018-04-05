import json
from random import SystemRandom
from string import ascii_letters
from typing import List

from bcrypt import gensalt
from bcrypt import hashpw
from flask import g
from flask import session
from flask_sqlalchemy import SQLAlchemy
from simplecrypt import encrypt
from sqlalchemy import func

from constant import Sites
from submission import Rating

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(16), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=True)
    email_verifier = db.Column(db.String(16), unique=True)
    email_verified = db.Column(db.Boolean, default=False)
    email_subscribed = db.Column(db.Boolean, default=False, nullable=False)

    accounts = db.relationship('Account', backref='user', lazy='dynamic')

    def __init__(self, username, password, email=None):
        self.username = username
        if email:
            self.email = email
        self.email_verifier = ''.join(SystemRandom().choice(ascii_letters) for _ in range(16))
        self.password = hashpw(password.encode('utf-8'), gensalt())

    def verify(self, password):
        self_password = self.password
        if hasattr(self_password, 'encode'):
            self_password = self_password.encode('utf-8')
        return hashpw(password.encode('utf-8'), self_password) == self_password

    @classmethod
    def by_name_or_email(cls, s):
        return cls.query.filter(
            (func.lower(cls.email) == func.lower(s)) | (func.lower(cls.username) == func.lower(s))).first()


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __init__(self, name):
        self.name = name

    @classmethod
    def names(cls) -> List[str]:
        return [site.name for site in cls.query.all()]


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(120), nullable=False)
    credentials = db.Column(db.LargeBinary, nullable=False)
    used_last = db.Column(db.Boolean, default=True)

    _site = db.relationship('Site', backref=db.backref('account', lazy='dynamic'))

    config = db.relationship('AccountConfig', lazy='dynamic', cascade='delete')

    def __init__(self, site, user_id, username, credentials):
        if isinstance(site, Sites):
            self.site_id = site.value
        else:
            self.site_id = site
        self.user_id = user_id
        self.username = username
        self.credentials = encrypt(session['password'], credentials)

    def update_credentials(self, credentials):
        self.credentials = encrypt(session['password'], credentials)

    def __getitem__(self, arg):
        return self.config.filter_by(key=arg).first()

    @property
    def site(self) -> Sites:
        return Sites(self.site_id)

    @classmethod
    def lookup_username(cls, site: Sites, uid: int, username: str):
        return cls.query.filter_by(site_id=site.value) \
            .filter_by(user_id=uid) \
            .filter(func.lower(Account.username) == func.lower(username)) \
            .first()


class AccountConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)

    key = db.Column(db.String(120), nullable=False)
    val = db.Column(db.String(120), nullable=False)

    account = db.relationship('Account', back_populates='config')

    def __init__(self, account_id, key, val):
        self.account_id = account_id
        self.key = key
        self.val = val


class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=1, nullable=False)

    def __init__(self, text):
        self.text = text

    def was_viewed_by(self, user):
        return NoticeViewed.query.filter_by(notice_id=self.id, user_id=user).first()

    @classmethod
    def find_active(cls):
        return cls.query.filter_by(active=True).order_by(cls.id.asc())


class NoticeViewed(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, notice, user):
        self.notice_id = notice
        self.user_id = user


class SavedSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Using Weasyl's lengths as restrictions here as they were easy to find
    title = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Enum(Rating), nullable=True)
    original_filename = db.Column(db.String(1000), nullable=True)
    image_filename = db.Column(db.String(1000), nullable=True)
    image_mimetype = db.Column(db.String(50), nullable=True)
    account_ids = db.Column(db.String(1000), nullable=True)
    site_data = db.Column(db.Text, nullable=True)  # arbitrary data stored as JSON

    group_id = db.Column(db.Integer, db.ForeignKey('submission_group.id'), nullable=True)

    def __init__(self, user=None, title=None, description=None, tags=None, rating=None):
        if user:
            self.user_id = user.id
        self.title = title
        self.description = description
        self.tags = tags
        self.rating = rating

    def set_accounts(self, ids):
        self.account_ids = ' '.join(ids)

    @property
    def accounts(self):
        if self.account_ids is None:
            return []

        return [Account.query.get(account) for account in self.account_ids.split(' ')]

    def all_selected_accounts(self, user):
        accounts = self.accounts
        all_accounts = user.accounts

        result = []

        for a in all_accounts:
            result.append({
                'account': a,
                'selected': a in accounts,
            })

        return result

    @property
    def data(self) -> dict:
        return json.loads(self.site_data) if self.site_data else {}

    @property
    def has_all(self) -> bool:
        return all(i is not None and i != '' for i in [self.title, self.description, self.tags, self.rating, self.account_ids, self.image_filename])

    @data.setter
    def data(self, value: dict) -> None:
        self.site_data = json.dumps(value)

    @classmethod
    def get_grouped(cls):
        return cls.query.filter_by(user_id=g.user.id).group_by(cls.group_id).order_by(
            cls.group_id.asc()).order_by(cls.id.asc()).all()


class SubmissionGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)

    def __init__(self, user, name):
        self.user_id = user.id
        self.name = name

    @classmethod
    def get_groups(cls):
        return cls.query.filter_by(user_id=g.user.id).all()

    @staticmethod
    def get_ungrouped_submissions():
        return SavedSubmission.query.filter_by(user_id=g.user.id).filter_by(group_id=None).all()

    @property
    def submissions(self):
        return SavedSubmission.query.filter_by(group_id=self.id).all()
