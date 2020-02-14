import json
from typing import Any, List

import tweepy
from flask import current_app, g, redirect, request, session
from werkzeug import Response

from constant import Sites
from models import Account, SavedSubmission, SubmissionGroup, db
from sentry import sentry
from sites import AccountExists, BadCredentials, Site, SiteError
from submission import Rating, Submission

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

        return {'me': me}

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
            json.dumps(
                {'token': session.pop('taccess'), 'secret': session.pop('tsecret')}
            ),
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

        tw_format: str = extra.get('twitter-format', '')
        links: list = extra.get('twitter-links')

        if use_custom_text == 'y':
            status = custom_text.strip()
        else:
            hashtags = submission.hashtags

            if submission.rating in (Rating.mature, Rating.explicit):
                if '#NSFW' not in (hashtag.upper() for hashtag in hashtags):
                    hashtags.append('#NSFW')

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

        try:
            noimage = self.account['twitter_noimage']

            if submission.rating == Rating.explicit and (
                noimage and noimage.val == 'yes'
            ):
                tweet = api.update_status(status=status, possibly_sensitive=True)
            else:
                filename, bytes = submission.resize_image(1280, 1280)

                tweet = api.update_with_media(
                    filename=filename,
                    file=bytes,
                    status=status,
                    possibly_sensitive=False
                    if submission.rating == Rating.general
                    else True,
                )
        except tweepy.TweepError as ex:
            raise SiteError(ex.reason)

        return 'https://twitter.com/{username}/status/{id}'.format(
            username=tweet.user.screen_name, id=tweet.id_str
        )

    def upload_group(self, group: SubmissionGroup, extra: Any = None):
        master: SavedSubmission = group.master
        s: Submission = master.submission
        submissions: List[SavedSubmission] = group.submissions

        images = list(self.collect_images(submissions, max_size=2000))

        auth = self._get_oauth_handler()
        auth.set_access_token(self.credentials['token'], self.credentials['secret'])

        api = tweepy.API(auth)

        data = master.data

        use_custom_text = data.get('twitter-custom', 'n')
        custom_text = data.get('twitter-custom-text')
        tw_format: str = data.get('twitter-format', '')

        links: list = extra.get('twitter-links')

        if use_custom_text == 'y':
            status = custom_text.strip()
        else:
            status = '{title} {hashtags}'.format(
                title=master.title, hashtags=self.tag_str(s.hashtags)
            ).strip()

        if links:
            if tw_format == 'single' or tw_format == '':
                status = status + ' ' + links[0][1]
            elif tw_format == 'multi':
                status += '\n'

                for link in links:
                    name = SHORT_NAMES[link[0]]
                    status += '\n{name}: {link}'.format(name=name, link=link[1])

        try:
            media_ids = []
            for image in images:
                res = api.media_upload(
                    filename=image['original_filename'], file=image['bytes']
                )
                media_ids.append(res.media_id)

            tweet = api.update_status(
                status=status,
                media_ids=media_ids,
                possibly_sensitive=False if s.rating == Rating.general else True,
            )

        except tweepy.TweepError as ex:
            raise SiteError(ex.reason)

        return 'https://twitter.com/{username}/status/{id}'.format(
            username=tweet.user.screen_name, id=tweet.id_str
        )

    @staticmethod
    def supports_group() -> bool:
        return True
