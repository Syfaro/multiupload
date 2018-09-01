import json

from mastodon import Mastodon as MastodonAPI
from flask import current_app, redirect, request, session
from urllib.parse import urlparse

from constant import Sites
from models import db, Account
from sites import Site


class MastodonApp(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    url = db.Column(db.String, unique=True)
    client_id = db.Column(db.String)
    client_secret = db.Column(db.String)

    def __init__(self, url, client_id, client_secret):
        self.url = url.lower()
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    def get_for_url(cls, url):
        return cls.query.filter_by(url=url.lower()).first()


class Mastodon(Site):
    SITE = Sites.Mastodon

    def __init__(self, credentials=None, account=None):
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def pre_add_account(self):
        url = 'https://foxesare.sexy'

        app = MastodonApp.get_for_url(url)
        if not app:
            client_id, client_secret = MastodonAPI.create_app(
                'Furry Multiuploader',
                scopes=current_app.config['MASTODON_SCOPES'],
                redirect_uris=current_app.config['MASTODON_CALLBACK'],
                website=current_app.config['MASTODON_WEBSITE'],
                api_base_url=url,
            )

            app = MastodonApp(url, client_id, client_secret)
            db.session.add(app)
            db.session.commit()

        api = MastodonAPI(
            app.client_id,
            app.client_secret,
            api_base_url=url,
        )

        return redirect(api.auth_request_url(
            redirect_uris=current_app.config['MASTODON_CALLBACK'],
            scopes=current_app.config['MASTODON_SCOPES'],
        ))

    def add_account_callback(self) -> dict:
        url = 'https://foxesare.sexy'
        app = MastodonApp.get_for_url(url)

        verifier_code = request.args.get('code')

        api = MastodonAPI(
            app.client_id,
            app.client_secret,
            api_base_url=url,
        )

        access_token = api.log_in(
            code=verifier_code,
            redirect_uri=current_app.config['MASTODON_CALLBACK'],
            scopes=current_app.config['MASTODON_SCOPES'],
        )

        user_info = api.account_verify_credentials()

        parsed = urlparse(url)

        return {
            'access_token': access_token,
            'user': '@{username}@{domain}'.format(
                username=user_info['username'],
                domain=parsed.netloc,
            )
        }

    def add_account(self, data: dict) -> Account:
        username = request.form.get('username')
        access_token = request.form.get('access_token')

        account = Account(self.SITE, session['id'], username, json.dumps({
            'access_token': access_token,
        }))

        db.session.add(account)
        db.session.commit()

        return account

    @staticmethod
    def supports_group() -> bool:
        return True
