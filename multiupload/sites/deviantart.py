import json
from typing import Any, Dict, List
from urllib.parse import urlencode

import requests
from flask import current_app, flash, g, redirect, request, session
from werkzeug import Response

from multiupload.constant import HEADERS, Sites
from multiupload.models import Account, AccountData, db
from multiupload.sites import (
    AccountExists,
    BadCredentials,
    BadData,
    MissingAccount,
    MissingCredentials,
    Site,
    SiteError,
)
from multiupload.submission import Rating, Submission

AUTH_ENDPOINT = 'https://www.deviantart.com/oauth2/authorize'
TOKEN_ENDPOINT = 'https://www.deviantart.com/oauth2/token'
PLACEBO_CALL = 'https://www.deviantart.com/api/v1/oauth2/placebo'
CATEGORY_TREE = 'https://www.deviantart.com/api/v1/oauth2/browse/categorytree'


class DeviantArtAPI(object):
    client_id = None
    client_secret = None

    redirect = None
    scope = None

    def __init__(
        self, client_id: str, client_secret: str, redirect: str, scope: str
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect = redirect
        self.scope = scope

    def auth_url(self, state: str = '') -> str:
        return (
            AUTH_ENDPOINT
            + '?'
            + urlencode(
                {
                    'response_type': 'code',
                    'client_id': self.client_id,
                    'redirect_uri': self.redirect,
                    'scope': self.scope,
                    'state': state,
                }
            )
        )

    def access_token(self, code: str) -> Dict[str, Any]:
        return requests.post(
            TOKEN_ENDPOINT,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.redirect,
            },
        ).json()

    def refresh_token(self, refresh: str) -> Dict[str, Any]:
        return requests.post(
            TOKEN_ENDPOINT,
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh,
            },
        ).json()

    @staticmethod
    def validate_token(token: str) -> Dict[str, Any]:
        return requests.post(PLACEBO_CALL, data={'access_token': token}).json()


class DeviantArt(Site):
    """DeviantArt."""

    SITE = Sites.DeviantArt

    def pre_add_account(self) -> Response:
        da = self.get_da()

        return redirect(da.auth_url())

    def add_account_callback(self) -> dict:
        da = self.get_da()

        code = request.args.get('code')
        if not code:
            raise BadData()

        r = da.access_token(code)

        if r['status'] == 'success':
            session['da_refresh'] = r['refresh_token']

            user = requests.post(
                'https://www.deviantart.com/api/v1/oauth2/user/whoami',
                headers=HEADERS,
                data={'access_token': r['access_token']},
            ).json()

            return {'user': user['username']}

        return {}

    def add_account(self, data: dict) -> Account:
        da = self.get_da()

        r = da.refresh_token(session['da_refresh'])

        user = requests.post(
            'https://www.deviantart.com/api/v1/oauth2/user/whoami',
            headers=HEADERS,
            data={'access_token': r['access_token']},
        ).json()

        if Account.lookup_username(self.SITE, g.user.id, user['username']):
            raise AccountExists()

        account = Account(
            self.SITE, session['id'], user['username'], r['refresh_token']
        )

        db.session.add(account)
        db.session.commit()

        return account

    @staticmethod
    def _build_exception(resp: dict) -> SiteError:
        desc = resp.get('error_description')
        if not desc:
            return SiteError('Unknown error')

        details = resp.get('error_details')

        msg = desc

        if details:
            msg += ': ' + ', '.join('{} - {}'.format(k, v) for k, v in details.items())

        return SiteError(msg)

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        da = self.get_da()

        if not self.credentials or not isinstance(self.credentials, str):
            raise MissingCredentials()

        r = da.refresh_token(self.credentials)
        if not self.account:
            raise MissingAccount()
        self.account.update_credentials(r['refresh_token'])
        db.session.commit()

        if r['status'] != 'success':
            raise BadCredentials()

        tags = {}
        for idx, tag in enumerate(submission.tags):
            tags['tags[{idx}]'.format(idx=idx)] = tag

        sub = requests.post(
            'https://www.deviantart.com/api/v1/oauth2/stash/submit',
            headers=HEADERS,
            data={
                'access_token': r['access_token'],
                'title': submission.title,
                'artist_comments': submission.description_for_site(self.SITE),
                **tags,
            },
            files={'image': submission.get_image()},
        ).json()

        if sub['status'] != 'success':
            raise DeviantArt._build_exception(sub)

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

        if isinstance(extra, dict):
            folders = extra.get('da-folders')
        else:
            folders = None

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
            data=data,
        ).json()

        if pub['status'] != 'success':
            raise SiteError(pub['error_description'])

        return pub['url']

    def get_folders(self, update: bool = False) -> List[dict]:
        if not self.account:
            raise MissingAccount()

        if not self.credentials or not isinstance(self.credentials, str):
            raise MissingCredentials()

        prev_folders: AccountData = self.account.data.filter_by(key='folders').first()
        if prev_folders and not update:
            return prev_folders.json

        da = self.get_da()

        r = da.refresh_token(self.credentials)
        self.account.update_credentials(r['refresh_token'])
        db.session.commit()

        all_folders: List[dict] = []

        while True:
            data = {'access_token': r['access_token'], 'limit': 50}

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
            if not self.account:
                raise MissingAccount()
            prev_folders = AccountData(self.account, 'folders', all_folders)
            db.session.add(prev_folders)

        db.session.commit()

        return all_folders

    @staticmethod
    def get_da() -> DeviantArtAPI:
        return DeviantArtAPI(
            current_app.config['DEVIANTART_KEY'],
            current_app.config['DEVIANTART_SECRET'],
            current_app.config['DEVIANTART_CALLBACK'],
            current_app.config['DEVIANTART_SCOPES'],
        )

    @staticmethod
    def supports_folder() -> bool:
        return True
