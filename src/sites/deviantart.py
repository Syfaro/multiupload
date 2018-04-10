import json
from typing import Any
from urllib.parse import urlencode

import requests
from flask import Response, flash
from flask import current_app
from flask import g
from flask import redirect
from flask import request
from flask import session

from constant import HEADERS
from constant import Sites
from models import Account, AccountData
from models import db
from sites import AccountExists
from sites import BadCredentials
from sites import Site
from sites import SiteError
from submission import Rating
from submission import Submission

AUTH_ENDPOINT = 'https://www.deviantart.com/oauth2/authorize'
TOKEN_ENDPOINT = 'https://www.deviantart.com/oauth2/token'
PLACEBO_CALL = 'https://www.deviantart.com/api/v1/oauth2/placebo'
CATEGORY_TREE = 'https://www.deviantart.com/api/v1/oauth2/browse/categorytree'


class DeviantArtAPI(object):
    client_id = None
    client_secret = None

    redirect = None
    scope = None

    def __init__(self, client_id, client_secret, redirect, scope):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect = redirect
        self.scope = scope

    def auth_url(self, state=''):
        return AUTH_ENDPOINT + '?' + urlencode({
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect,
            'scope': self.scope,
            'state': state,
        })

    def access_token(self, code):
        return requests.post(TOKEN_ENDPOINT, data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect,
        }).json()

    def refresh_token(self, refresh):
        return requests.post(TOKEN_ENDPOINT, data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh,
        }).json()

    @staticmethod
    def validate_token(token):
        return requests.post(PLACEBO_CALL, data={
            'access_token': token,
        }).json()


class DeviantArt(Site):
    """DeviantArt."""
    SITE = Sites.DeviantArt

    def pre_add_account(self) -> Response:
        da = self.get_da()

        return redirect(da.auth_url())

    def add_account_callback(self) -> dict:
        da = self.get_da()

        r = da.access_token(request.args.get('code'))

        if r['status'] == 'success':
            session['da_refresh'] = r['refresh_token']

            user = requests.post('https://www.deviantart.com/api/v1/oauth2/user/whoami', headers=HEADERS, data={
                'access_token': r['access_token']
            }).json()

            return {'user': user['username']}

        return {}

    def add_account(self, data: dict) -> Account:
        da = self.get_da()

        r = da.refresh_token(session['da_refresh'])

        user = requests.post('https://www.deviantart.com/api/v1/oauth2/user/whoami', headers=HEADERS, data={
            'access_token': r['access_token'],
        }).json()

        if Account.lookup_username(self.SITE, g.user.id, user['username']):
            raise AccountExists()

        account = Account(
            self.SITE,
            session['id'],
            user['username'],
            r['refresh_token']
        )

        db.session.add(account)
        db.session.commit()

        return account

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        da = self.get_da()

        r = da.refresh_token(self.credentials)
        self.account.update_credentials(r['refresh_token'])
        db.session.commit()

        if r['status'] != 'success':
            raise BadCredentials()

        sub = requests.post('https://www.deviantart.com/api/v1/oauth2/stash/submit', headers=HEADERS, data={
            'access_token': r['access_token'],
            'title': submission.title,
            'artist_comments': submission.description_for_site(self.SITE),
            'tags': self.tag_str(submission.tags),
        }, files={
            'image': submission.get_image(),
        }).json()

        if sub['status'] != 'success':
            raise SiteError(sub['error_description'])

        itemid = sub['itemid']

        is_mature = '0'
        mature_level = None

        if submission.rating == Rating.general:
            is_mature = '0'
        elif submission.rating == Rating.mature:
            is_mature = '1'
            mature_level = 'moderate'
        elif submission.rating == Rating.explicit:
            is_mature = '1'
            mature_level = 'strict'

        data = {
            'access_token': r['access_token'],
            'itemid': itemid,
            'agree_submission': '1',
            'agree_tos': '1',
            'is_mature': is_mature,
            'catpath': request.form.get('deviantart-category'),
        }

        folders = extra.get('da-folders')
        if folders:
            try:
                folders = json.loads(folders)
                account = folders.get(str(self.account.id))

                if account:
                    if 'None' not in account:
                        data['galleryids'] = self.tag_str(account)
            except json.decoder.JSONDecodeError:
                pass

        if mature_level:
            data['mature_level'] = mature_level
            data['mature_classification'] = request.form.getlist('da-content')

        pub = requests.post(
            'https://www.deviantart.com/api/v1/oauth2/stash/publish',
            headers=HEADERS,
            data=data
        ).json()

        if pub['status'] != 'success':
            raise SiteError(pub['error_description'])

        return pub['url']

    def get_folders(self, update=False):
        prev_folders: AccountData = self.account.data.filter_by(key='folders').first()
        if prev_folders and not update:
            return prev_folders.json

        da = self.get_da()

        r = da.refresh_token(self.credentials)
        self.account.update_credentials(r['refresh_token'])
        db.session.commit()

        all_folders = []

        while True:
            data = {
                'access_token': r['access_token'],
                'limit': 50,
            }

            if all_folders:
                data['next_offset'] = all_folders[-1].get('folderid')

            try:
                folders = requests.get(
                    'https://www.deviantart.com/api/v1/oauth2/gallery/folders',
                    headers=HEADERS,
                    params=data,
                ).json()
            except json.decoder.JSONDecodeError:
                raise SiteError('Unable to get data.')

            results = folders.get('results')
            if not results:
                flash('Unable to get DeviantArt folders')
                break

            all_folders.extend(results)

            if not folders.get('has_more'):
                break

        if prev_folders:
            prev_folders.json = all_folders
        else:
            prev_folders = AccountData(self.account, 'folders', all_folders)
            db.session.add(prev_folders)

        db.session.commit()

        return all_folders

    @staticmethod
    def get_da():
        return DeviantArtAPI(current_app.config['DEVIANTART_KEY'], current_app.config['DEVIANTART_SECRET'],
                             current_app.config['DEVIANTART_CALLBACK'], current_app.config['DEVIANTART_SCOPES'])
