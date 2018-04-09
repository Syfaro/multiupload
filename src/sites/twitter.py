import json
from typing import Any

import tweepy
from flask import Response
from flask import current_app
from flask import g
from flask import redirect
from flask import request
from flask import session

from constant import Sites
from models import Account
from models import db
from sentry import sentry
from sites import AccountExists
from sites import BadCredentials
from sites import Site
from sites import SiteError
from submission import Rating
from submission import Submission


SHORT_NAMES = {
    Sites.FurAffinity: 'FA',
    Sites.Weasyl: 'Weasyl',
    Sites.FurryNetwork: 'FN',
    Sites.Inkbunny: 'IB',
    Sites.SoFurry: 'SF',
    Sites.Tumblr: 'Tumblr',
    Sites.DeviantArt: 'DA',
    Sites.Twitter: 'Twitter',
}


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

    def add_account_callback(self) -> dict:
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

        api = tweepy.API(auth)
        me = api.me()

        return {
            'me': me,
        }

    def add_account(self, data: dict) -> Account:
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
                'token': session.pop('taccess'),
                'secret': session.pop('tsecret'),
            })
        )

        db.session.add(account)
        db.session.commit()

        return account

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        auth = self._get_oauth_handler()
        auth.set_access_token(self.credentials['token'], self.credentials['secret'])

        api = tweepy.API(auth)

        use_custom_text = extra.get('twitter-custom', 'n')
        custom_text = extra.get('twitter-custom-text')

        format: str = extra.get('twitter-format', '')
        links: list = extra.get('twitter-links')

        if use_custom_text == 'y':
            status = custom_text.strip()
        else:
            status = '{title} {hashtags}'.format(title=submission.title,
                                                 hashtags=self.tag_str(submission.hashtags)).strip()

        if links:
            if format == 'single' or format == '':
                    status = status + ' ' + links[0][1]
            elif format == 'multi':
                status += '\n'

                for link in links:
                    name = SHORT_NAMES[link[0]]
                    status += '\n{name}: {link}'.format(name=name, link=link[1])

        try:
            tweet = api.update_with_media(filename=submission.image_filename,
                                          file=submission.image_bytes, status=status,
                                          possibly_sensitive=False if submission.rating == Rating.general else True)
        except tweepy.TweepError as ex:
            raise SiteError(ex.reason)

        return 'https://twitter.com/{username}/status/{id}'.format(username=tweet.user.screen_name, id=tweet.id_str)
