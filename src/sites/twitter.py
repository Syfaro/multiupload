from typing import Any

from flask import g
from flask import session
from flask import current_app
from flask import redirect
from flask import request
from flask import Response

import json
import tweepy

from models import db
from models import Account

from sentry import sentry

from constant import Sites

from sites import Site
from sites import BadCredentials
from sites import AccountExists
from sites import SiteError

from submission import Submission
from submission import Rating


class Twitter(Site):
    """Twitter."""
    SITE = Sites.Twitter

    def __init__(self, credentials=None, account=None):
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    @staticmethod
    def _get_oauth_handler() -> tweepy.OAuthHandler:
        key = current_app.config['TWITTER_KEY']
        secret = current_app.config['TWITTER_SECRET']
        callback = current_app.config['TWITTER_CALLBACK']

        return tweepy.OAuthHandler(key, secret, callback)

    def pre_add_account(self) -> Response:
        auth = self._get_oauth_handler()

        try:
            auth_url = auth.get_authorization_url()
        except tweepy.TweepError:
            sentry.captureException()

            raise SiteError('An error occurred with Twitter.')

        session['request_token'] = auth.request_token

        return redirect(auth_url)

    def add_account_callback(self, data: Any) -> None:
        verifier = request.args.get('oauth_verifier', None)
        token = session.pop('request_token', None)
        auth = self._get_oauth_handler()
        auth.request_token = token

        try:
            auth.get_access_token(verifier)
        except tweepy.TweepError:
            raise BadCredentials()

        session['taccess'] = auth.access_token
        session['tsecret'] = auth.access_token_secret

    def parse_add_form(self, form) -> dict:
        print('Twitter parse_add_form')
        return {}

    def add_account(self, data: dict) -> None:
        auth = self._get_oauth_handler()
        auth.set_access_token(session['taccess'], session['tsecret'])

        api = tweepy.API(auth)
        me = api.me()

        if Account.lookup_username(self.SITE, g.user.id, me.screen_name):
            raise AccountExists()

        account = Account(
            self.SITE,
            session['id'],
            me.screen_name,
            json.dumps({
                'token': session.pop('taccesss'),
                'secret': session.pop('tsecret'),
            })
        )

        db.session.add(account)
        db.session.commit()

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        auth = self._get_oauth_handler()
        auth.set_access_token(self.credentials['token'], self.credentials['secret'])

        api = tweepy.API(auth)

        status = '{title} {hashtags}'.format(title=submission.title, hashtags=self.tag_str(submission.hashtags))

        if isinstance(extra, dict):
            link = extra.get('twitter_link', None)
            if link:
                status = status.strip() + ' ' + link

        try:
            tweet = api.update_with_media(filename=submission.image_filename,
                                          file=submission.image_bytes, status=status,
                                          possibly_sensitive=False if submission.rating == Rating.general else True)
        except tweepy.TweepError as ex:
            raise SiteError(ex.reason)

        return 'https://twitter.com/{username}/status/{id}'.format(username=tweet.user.screen_name, id=tweet.id_str)
