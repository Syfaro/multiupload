import json
from typing import Any
from urllib.parse import urlparse

from flask import current_app, flash, redirect, request, session, url_for
from mastodon import Mastodon as MastodonAPI

from constant import Sites
from models import Account, db
from sites import Site
from sites.twitter import SHORT_NAMES
from submission import Rating, Submission


class MastodonApp(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    url = db.Column(db.String(255), unique=True)
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))

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
        url = request.args.get('domain')
        if not url:
            flash('Missing domain name')
            return redirect(url_for('accounts.manage'))

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

        session['MASTODON_URL'] = url

        return redirect(api.auth_request_url(
            redirect_uris=current_app.config['MASTODON_CALLBACK'],
            scopes=current_app.config['MASTODON_SCOPES'],
        ))

    def add_account_callback(self) -> dict:
        url = session.get('MASTODON_URL')
        app = MastodonApp.get_for_url(url)
        if not app:
            flash('Server issue, please try again')
            return redirect(url_for('accounts.manage'))

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
        url = session.pop('MASTODON_URL')

        username = request.form.get('username')
        access_token = request.form.get('access_token')

        account = Account(self.SITE, session['id'], username, json.dumps({
            'access_token': access_token,
            'url': url,
        }))

        db.session.add(account)
        db.session.commit()

        return account

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        url = self.credentials['url']
        app = MastodonApp.get_for_url(url)

        api = MastodonAPI(
            app.client_id,
            app.client_secret,
            api_base_url=url,
            access_token=self.credentials['access_token'],
        )

        use_custom_text = extra.get('twitter-custom', 'n')
        custom_text = extra.get('twitter-custom-text')

        tw_format: str = extra.get('twitter-format', '')
        links: list = extra.get('twitter-links')

        is_sensitive = True if submission.rating in (Rating.mature, Rating.explicit) else False

        if use_custom_text == 'y':
            status = custom_text.strip()
        else:
            hashtags = submission.hashtags

            hashtags_str = self.tag_str(hashtags)

            status = '{title} {hashtags}'.format(
                title=submission.title, hashtags=hashtags_str.strip()
            )

        if links:
            if tw_format == 'single' or tw_format == '':
                status = status + ' ' + links[0][1]
            elif tw_format == 'multi':
                status += '\n'

                for link in links:
                    name = SHORT_NAMES[link[0]]
                    status += '\n{name}: {link}'.format(name=name, link=link[1])

        noimage = self.account['twitter_noimage']

        content_warning: str = extra.get('mastodon-warning', None)
        image_desc: str = extra.get('mastodon-image-desc', None)

        if content_warning == '':
            content_warning = None

        if image_desc == '':
            image_desc = None

        if submission.rating == Rating.explicit and (
            noimage and noimage.val == 'yes'
        ):
            status = api.status_post(status=status, sensitive=is_sensitive, visibility='public', spoiler_text=content_warning)
        else:
            media = api.media_post(submission.image_bytes, mime_type=submission.image_mimetype, description=image_desc)
            status = api.status_post(status=status, sensitive=is_sensitive, visibility='public', media_ids=media, spoiler_text=content_warning)

        return status['url']
