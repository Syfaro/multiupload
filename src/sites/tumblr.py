import json
from typing import Any
from typing import List

import tumblpy
from flask import Response
from flask import current_app
from flask import flash
from flask import redirect
from flask import request
from flask import session

from constant import Sites
from models import Account
from models import db
from sites import BadCredentials
from sites import Site
from sites import SiteError
from submission import Submission
from utils import tumblr_blog_name


class Tumblr(Site):
    """Tumblr."""
    SITE = Sites.Tumblr

    def __init__(self, credentials=None, account=None):
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def pre_add_account(self) -> Response:
        tumblr = tumblpy.Tumblpy(current_app.config['TUMBLR_KEY'], current_app.config['TUMBLR_SECRET'])
        auth_props = tumblr.get_authentication_tokens(current_app.config['TUMBLR_CALLBACK'])

        session['tumblr_token'] = auth_props['oauth_token_secret']

        return redirect(auth_props['auth_url'])

    def add_account_callback(self) -> dict:
        verifier = request.args.get('oauth_verifier', None)
        token = request.args.get('oauth_token', None)

        tumblr = tumblpy.Tumblpy(current_app.config['TUMBLR_KEY'], current_app.config['TUMBLR_SECRET'],
                                 token, session['tumblr_token'])

        try:
            authorized_tokens = tumblr.get_authorized_tokens(verifier)
        except tumblpy.TumblpyError as ex:
            raise SiteError(ex.msg)

        session['tumblr_token'] = authorized_tokens['oauth_token']
        session['tumblr_secret'] = authorized_tokens['oauth_token_secret']

        tumblr = tumblpy.Tumblpy(current_app.config['TUMBLR_KEY'], current_app.config['TUMBLR_SECRET'],
                                 session['tumblr_token'], session['tumblr_secret'])

        try:
            return {
                'user': tumblr.post('user/info'),
            }
        except tumblpy.TumblpyAuthError as ex:
            raise SiteError(ex.msg)

    def add_account(self, data: dict) -> None:
        t = tumblpy.Tumblpy(current_app.config['TUMBLR_KEY'], current_app.config['TUMBLR_SECRET'],
                            session['tumblr_token'], session['tumblr_secret'])

        resp = t.post('user/info')

        for blog in resp['user']['blogs']:
            url = tumblr_blog_name(blog['url'])

            if Account.lookup_username(self.SITE, session['id'], url):
                flash('Account {url} already exists, skipping.'.format(url=url))
                continue

            account = Account(
                self.SITE,
                session['id'],
                tumblr_blog_name(url),
                json.dumps({
                    'token': session['tumblr_token'],
                    'secret': session['tumblr_secret'],
                })
            )

            db.session.add(account)

        session.pop('tumblr_token')
        session.pop('tumblr_secret')

        db.session.commit()

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        t = tumblpy.Tumblpy(current_app.config['TUMBLR_KEY'], current_app.config['TUMBLR_SECRET'],
                            self.credentials['token'], self.credentials['secret'])

        if self.account['tumblr_title'] and self.account['tumblr_title'].val == 'yes':
            submission.description = '## ' + submission.title + '\n\n' + submission.description

        try:
            res = t.post('post', blog_url=self.account.username, params={
                'type': 'photo',
                'caption': submission.description_for_site(self.SITE),
                'data': submission.image_bytes,
                'state': 'published',
                'format': 'markdown',
                'tags': self.tag_str(submission.tags),
            })
        except tumblpy.TumblpyError as ex:
            raise SiteError(ex.msg)

        post_id = res.get('id', None)

        if not post_id:
            raise BadCredentials()

        return 'https://{url}/post/{id}'.format(url=self.account.username, id=post_id)

    def tag_str(self, tags: List[str]) -> str:
        return ' ,'.join(tags)
