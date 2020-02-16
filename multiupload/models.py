import json
from random import SystemRandom
from string import ascii_letters
from typing import Any, Dict, List, Optional, Union

from authlib.integrations.sqla_oauth2 import (
    OAuth2AuthorizationCodeMixin,
    OAuth2ClientMixin,
    OAuth2TokenMixin,
)
from bcrypt import gensalt, hashpw
from flask import g, session
from flask_sqlalchemy import SQLAlchemy
from simplecrypt import encrypt
from sqlalchemy import func
from sqlalchemy.orm import Query

from multiupload.constant import Sites
from multiupload.submission import Rating, Submission

db = SQLAlchemy()


class User(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(16), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    email = db.Column(db.String(254), unique=True, nullable=True)
    email_verifier = db.Column(db.String(16), unique=True)
    email_verified = db.Column(db.Boolean, default=False)
    email_subscribed = db.Column(db.Boolean, default=False, nullable=False)
    email_reset_verifier = db.Column(db.String(16), unique=True)

    theme = db.Column(db.String(255), nullable=True)
    theme_url = db.Column(db.String(255), nullable=True)

    save_errors = db.Column(db.Boolean, nullable=False, default=False)

    accounts = db.relationship('Account', backref='user', lazy='dynamic')

    def __init__(self, username: str, password: str, email: str = None):
        self.username = username
        if email:
            self.email = email
        self.email_verifier = ''.join(
            SystemRandom().choice(ascii_letters) for _ in range(16)
        )
        self.password = hashpw(password.encode('utf-8'), gensalt())
        self.save_errors = False

    def verify(self, password: str) -> bool:
        self_password = self.password
        if hasattr(self_password, 'encode'):
            self_password = self_password.encode('utf-8')
        return hashpw(password.encode('utf-8'), self_password) == self_password

    @classmethod
    def by_name_or_email(cls, s: str) -> Optional['User']:
        return cls.query.filter(
            (func.lower(cls.email) == func.lower(s))
            | (func.lower(cls.username) == func.lower(s))
        ).first()

    def get_user_id(self) -> int:
        return self.id


class Site(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def names(cls) -> List[str]:
        return [site.name for site in cls.query.all()]


class Account(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(120), nullable=False)
    credentials = db.Column(db.LargeBinary, nullable=False)
    used_last = db.Column(db.Boolean, default=True)

    _site = db.relationship('Site', backref=db.backref('account', lazy='dynamic'))

    config = db.relationship('AccountConfig', lazy='dynamic', cascade='delete')
    data = db.relationship('AccountData', lazy='dynamic', cascade='delete')

    def __init__(
        self, site: Union[Sites, int], user_id: int, username: str, credentials: str
    ):
        if isinstance(site, Sites):
            self.site_id = site.value
        else:
            self.site_id = site
        self.user_id = user_id
        self.username = username
        self.credentials = encrypt(session['password'], credentials)

    def update_credentials(self, credentials: str) -> None:
        self.credentials = encrypt(session['password'], credentials)

    def __getitem__(self, arg: str) -> Optional['AccountConfig']:
        return self.config.filter_by(key=arg).first()

    @property
    def site(self) -> Sites:
        return Sites(self.site_id)

    @classmethod
    def find(cls, account_id: int) -> Optional['Account']:
        return cls.query.filter_by(id=account_id).filter_by(user_id=g.user.id).first()

    @classmethod
    def all(cls) -> List['Account']:
        return (
            cls.query.filter_by(user_id=g.user.id)
            .order_by(cls.site_id.asc())
            .order_by(cls.username.asc())
            .all()
        )

    @classmethod
    def lookup_username(
        cls, site: Sites, uid: int, username: str
    ) -> Optional['Account']:
        return (
            cls.query.filter_by(site_id=site.value)
            .filter_by(user_id=uid)
            .filter(func.lower(Account.username) == func.lower(username))
            .first()
        )


class AccountConfig(db.Model):  # type: ignore
    """A setting for an account. Uses short string key/value pairs."""

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)

    key = db.Column(db.String(120), nullable=False)
    val = db.Column(db.String(120), nullable=False)

    account = db.relationship('Account', back_populates='config')

    def __init__(self, account_id: int, key: str, val: str):
        self.account_id = account_id
        self.key = key
        self.val = val

    def __repr__(self) -> str:
        return '<AccountConfig {id}, {account_id}, {key}: {value}>'.format(
            id=self.id, account_id=self.account_id, key=self.key, value=self.val
        )


class AccountData(db.Model):  # type: ignore
    """Data associated to an account. Uses a short key with a JSON value."""

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)

    key = db.Column(db.String(120), nullable=False)
    data = db.Column(db.Text, nullable=False)

    account = db.relationship('Account', back_populates='data')

    # TODO: make account consistent
    def __init__(self, account: Union[Account, int], key: str, data: Any):
        if isinstance(account, Account):
            self.account_id = account.id
        else:
            self.account_id = account

        self.key = key
        self.data = json.dumps(data)

    @property
    def json(self) -> Any:
        return json.loads(self.data)

    @json.setter
    def json(self, data: Any) -> None:
        self.data = json.dumps(data)


class Notice(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=1, nullable=False)

    def __init__(self, text: str):
        self.text = text

    def was_viewed_by(self, user: int) -> Optional['Notice']:
        return NoticeViewed.query.filter_by(notice_id=self.id, user_id=user).first()

    @classmethod
    def find_active(cls) -> Query:
        return cls.query.filter_by(active=True).order_by(cls.id.asc())


class NoticeViewed(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)

    notice_id = db.Column(db.Integer, db.ForeignKey('notice.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, notice: int, user: int):
        self.notice_id = notice
        self.user_id = user


class SavedSubmission(db.Model):  # type: ignore
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

    group_id = db.Column(
        db.Integer, db.ForeignKey('submission_group.id'), nullable=True
    )
    master = db.Column(db.Boolean, default=False, nullable=False)

    def __init__(
        self,
        user: User = None,
        title: str = None,
        description: str = None,
        tags: str = None,
        rating: Rating = None,
    ):
        if user:
            self.user_id = user.id
        self.title = title
        self.description = description
        self.tags = tags
        self.rating = rating

    def set_accounts(self, ids: List[str]) -> None:
        self.account_ids = ' '.join([str(i) for i in ids])

    @property
    def group(self) -> Optional['SubmissionGroup']:
        return (
            SubmissionGroup.query.filter_by(user_id=g.user.id)
            .filter_by(id=self.group_id)
            .first()
        )

    @property
    def accounts(self) -> List[Account]:
        if self.account_ids is None:
            return []

        account_ids = self.account_ids.split(' ')

        accounts = []

        for account in account_ids:
            if not account:
                continue

            find = Account.find(int(account))
            if find:
                accounts.append(find)

        return accounts

    def all_selected_accounts(self, user: User) -> List[Dict[str, bool]]:
        accounts = self.accounts
        all_accounts = user.accounts

        result = []

        for a in all_accounts:
            result.append({'account': a, 'selected': a in accounts})

        result = sorted(result, key=lambda a: a['account'].site.name)

        return result

    @property
    def submission(self) -> Submission:
        return Submission(
            self.title, self.description, self.tags, self.rating.value, self
        )

    def has_all(self, ignore_sites: bool = False) -> bool:
        return all(
            i is not None and i != ''
            for i in [
                self.title,
                self.description,
                self.tags,
                self.rating,
                self.account_ids if not ignore_sites else 'hi',
                self.image_filename,
            ]
        )

    @property
    def data(self) -> dict:
        return json.loads(self.site_data) if self.site_data else {}

    @data.setter
    def data(self, value: dict) -> None:
        self.site_data = json.dumps(value)

    @classmethod
    def get_grouped(cls) -> List['SavedSubmission']:
        return (
            cls.query.filter_by(user_id=g.user.id)
            .filter_by(master=False)
            .group_by(cls.group_id)
            .order_by(cls.group_id.asc())
            .order_by(cls.id.asc())
            .all()
        )

    @classmethod
    def find(cls, sub_id: int) -> Optional['SavedSubmission']:
        return cls.query.filter_by(user_id=g.user.id).filter_by(id=sub_id).first()


class SubmissionGroup(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    grouped = db.Column(db.Boolean, default=False)

    def __init__(self, user: User, name: str, grouped: bool = False):
        self.user_id = user.id
        self.name = name
        self.grouped = grouped

    @classmethod
    def get_groups(cls) -> List['SubmissionGroup']:
        return cls.query.filter_by(user_id=g.user.id).all()

    @staticmethod
    def get_ungrouped_submissions() -> List[SavedSubmission]:
        return (
            SavedSubmission.query.filter_by(user_id=g.user.id)
            .filter_by(group_id=None)
            .order_by(SavedSubmission.id.asc())
            .all()
        )

    @property
    def submittable(self) -> bool:
        return all([sub.has_all(ignore_sites=True) for sub in self.submissions])

    @property
    def submissions(self) -> List[SavedSubmission]:
        return (
            SavedSubmission.query.filter_by(group_id=self.id)
            .filter_by(master=False)
            .order_by(SavedSubmission.id.asc())
            .all()
        )

    @property
    def master(self) -> SavedSubmission:
        return (
            SavedSubmission.query.filter_by(group_id=self.id)
            .filter_by(master=True)
            .first()
        )

    @classmethod
    def find(cls, group_id: int) -> Optional['SubmissionGroup']:
        return cls.query.filter_by(user_id=g.user.id).filter_by(id=group_id).first()


class SavedTemplate(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    content = db.Column(db.String(1024), nullable=False)

    def __init__(self, user: Union[int, User], name: str, content: str):
        if isinstance(user, User):
            self.user_id = user.id
        else:
            self.user_id = user

        self.name = name
        self.content = content

    def as_dict(self) -> Dict[str, Any]:
        return {'id': self.id, 'name': self.name, 'content': self.content}


class MastodonApp(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)

    url = db.Column(db.String(255), unique=True)
    client_id = db.Column(db.String(255), nullable=False)
    client_secret = db.Column(db.String(255), nullable=False)

    def __init__(self, url: str, client_id: str, client_secret: str):
        self.url = url.lower()
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    def get_for_url(cls, url: str) -> Optional['MastodonApp']:
        return cls.query.filter_by(url=url.lower()).first()


class DeviantArtCategory(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)

    path = db.Column(db.String(255), unique=True)
    value = db.Column(db.Text, nullable=False)

    def __init__(self, path: str, value: bytes):
        self.path = path
        self.value = json.dumps(value.decode('utf-8'))

    @property
    def data(self) -> Any:
        return json.loads(self.value)

    @data.setter
    def data(self, data: bytes) -> None:
        self.value = json.dumps(data.decode('utf-8'))

    @classmethod
    def lookup_path(cls, path: str) -> Optional[Any]:
        result = cls.query.filter_by(path=path).first()

        if result:
            return result.data
        else:
            return None


class Client(db.Model, OAuth2ClientMixin):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    user = db.relationship('User')


class Token(db.Model, OAuth2TokenMixin):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    user = db.relationship('User')


class AuthorizationCode(db.Model, OAuth2AuthorizationCodeMixin):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    user = db.relationship('User')
