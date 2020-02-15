import json
from typing import Any, List, Optional

import tumblpy
from flask import current_app, flash, redirect, request, session
from werkzeug import Response

from multiupload.constant import Sites
from multiupload.models import Account, AccountData, SubmissionGroup, db
from multiupload.sites import (
    BadCredentials,
    BadData,
    MissingAccount,
    MissingCredentials,
    Site,
    SiteError,
)
from multiupload.submission import Submission
from multiupload.utils import tumblr_blog_name


class Tumblr(Site):
    """Tumblr."""

    SITE = Sites.Tumblr

    def __init__(
        self, credentials: Optional[str] = None, account: Optional[Account] = None
    ) -> None:
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def pre_add_account(self) -> Response:
        tumblr = tumblpy.Tumblpy(
            current_app.config['TUMBLR_KEY'], current_app.config['TUMBLR_SECRET']
        )
        auth_props = tumblr.get_authentication_tokens(
            current_app.config['TUMBLR_CALLBACK']
        )

        session['tumblr_token'] = auth_props['oauth_token_secret']

        return redirect(auth_props['auth_url'])

    def add_account_callback(self) -> dict:
        verifier = request.args.get('oauth_verifier', None)
        token = request.args.get('oauth_token', None)

        tumblr = tumblpy.Tumblpy(
            current_app.config['TUMBLR_KEY'],
            current_app.config['TUMBLR_SECRET'],
            token,
            session['tumblr_token'],
        )

        try:
            authorized_tokens = tumblr.get_authorized_tokens(verifier)
        except tumblpy.TumblpyError as ex:
            raise SiteError(ex.msg)

        session['tumblr_token'] = authorized_tokens['oauth_token']
        session['tumblr_secret'] = authorized_tokens['oauth_token_secret']

        tumblr = tumblpy.Tumblpy(
            current_app.config['TUMBLR_KEY'],
            current_app.config['TUMBLR_SECRET'],
            session['tumblr_token'],
            session['tumblr_secret'],
        )

        try:
            return {'user': tumblr.post('user/info')}
        except tumblpy.TumblpyAuthError as ex:
            raise SiteError(ex.msg)

    def add_account(self, data: dict) -> List[Account]:
        t = tumblpy.Tumblpy(
            current_app.config['TUMBLR_KEY'],
            current_app.config['TUMBLR_SECRET'],
            session['tumblr_token'],
            session['tumblr_secret'],
        )

        resp = t.post('user/info')

        accounts = []

        for blog in resp['user']['blogs']:
            url = tumblr_blog_name(blog['url'])

            if Account.lookup_username(self.SITE, session['id'], url):
                flash('Account {url} already exists, skipping.'.format(url=url))
                continue

            account = Account(
                self.SITE,
                session['id'],
                tumblr_blog_name(url),
                json.dumps(
                    {
                        'token': session['tumblr_token'],
                        'secret': session['tumblr_secret'],
                    }
                ),
            )
            accounts.append(account)
            db.session.add(account)
            db.session.commit()

            u = AccountData(account, 'url', blog['url'])
            db.session.add(u)
            db.session.commit()

        session.pop('tumblr_token')
        session.pop('tumblr_secret')

        return accounts

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        if not isinstance(self.credentials, dict):
            raise MissingCredentials()

        t = tumblpy.Tumblpy(
            current_app.config['TUMBLR_KEY'],
            current_app.config['TUMBLR_SECRET'],
            self.credentials['token'],
            self.credentials['secret'],
        )

        if not self.account:
            raise MissingCredentials()

        title = self.account['tumblr_title']

        if title and title.val == 'yes':
            if not submission.title or not submission.description:
                raise BadData()

            submission.description = (
                '## ' + submission.title + '\n\n' + submission.description
            )

        try:
            res = t.post(
                'post',
                blog_url=self.account.username,
                params={
                    'type': 'photo',
                    'caption': submission.description_for_site(self.SITE),
                    'data': submission.image_bytes,
                    'state': 'published',
                    'format': 'markdown',
                    'tags': self.tag_str(submission.tags),
                },
            )
        except tumblpy.TumblpyError as ex:
            raise SiteError(ex.msg)

        post_id = res.get('id', None)

        if not post_id:
            raise BadCredentials()

        url = 'http://' + self.account.username + '/'

        data: AccountData = self.account.data.filter_by(key='url').first()
        if data:
            url = data.json

        return '{url}post/{id}'.format(url=url, id=post_id)

    def tag_str(self, tags: List[str]) -> str:
        return ' ,'.join(tags)

    def upload_group(self, group: SubmissionGroup, extra: Any = None) -> str:
        if not isinstance(self.credentials, dict):
            raise MissingCredentials()

        t = tumblpy.Tumblpy(
            current_app.config['TUMBLR_KEY'],
            current_app.config['TUMBLR_SECRET'],
            self.credentials['token'],
            self.credentials['secret'],
        )

        master = group.master
        s = master.submission
        submissions = group.submissions

        images = self.collect_images(submissions)

        image_bytes = [image.data for image in images]

        if not self.account:
            raise MissingAccount()

        title = self.account['tumblr_title']

        if title and title.val == 'yes':
            master.description = '## ' + master.title + '\n\n' + master.description

        params = {
            'type': 'photo',
            'caption': s.description_for_site(self.SITE),
            'data': image_bytes,
            'state': 'published',
            'format': 'markdown',
            'tags': self.tag_str(s.tags),
        }

        for idx, image in enumerate(image_bytes):
            params['data[{0}]'.format(idx)] = image

        try:
            res = t.post('post', blog_url=self.account.username, params=params)
        except tumblpy.TumblpyError as ex:
            raise SiteError(ex.msg)

        post_id = res.get('id', None)

        if not post_id:
            raise BadCredentials()

        url = 'http://' + self.account.username + '/'

        data: AccountData = self.account.data.filter_by(key='url').first()
        if data:
            url = data.json

        return '{url}post/{id}'.format(url=url, id=post_id)

    @staticmethod
    def supports_group() -> bool:
        return True
