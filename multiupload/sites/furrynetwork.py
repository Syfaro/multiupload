import json
import re
from typing import Any, Dict, List, Optional

import cfscrape
from flask import flash, g, session
import simplecrypt

from multiupload.constant import HEADERS, Sites
from multiupload.models import Account, AccountData, db
from multiupload.sites import (
    BadCredentials,
    BadData,
    MissingAccount,
    MissingCredentials,
    Site,
    SiteError,
)
from multiupload.submission import Rating, Submission
from multiupload.utils import clear_recorded_pages, record_page, write_site_response


class FurryNetwork(Site):
    """FurryNetwork."""

    SITE = Sites.FurryNetwork

    def __init__(
        self, credentials: Optional[bytes] = None, account: Optional[Account] = None
    ) -> None:
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def parse_add_form(self, form: dict) -> dict:
        return {'username': form.get('email', ''), 'password': form.get('password', '')}

    def add_account(self, data: Optional[dict]) -> List[Account]:
        sess = cfscrape.create_scraper()

        assert data is not None

        req = sess.post(
            'https://beta.furrynetwork.com/api/oauth/token',
            data={
                'username': data['username'],
                'password': data['password'],
                'grant_type': 'password',
                'client_id': '123',
                'client_secret': '',
            },
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)

        j = req.json()

        refresh = j.get('refresh_token', None)
        if not refresh:
            raise BadCredentials()

        auth_headers = HEADERS.copy()
        auth_headers['Authorization'] = 'Bearer {access}'.format(
            access=j['access_token']
        )

        req = sess.get(
            'https://beta.furrynetwork.com/api/user',
            data={'user_id': j['user_id']},
            headers=auth_headers,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        previous_accounts = (
            Account.query.filter_by(user_id=g.user.id)
            .filter_by(site_id=self.SITE.value)
            .all()
        )

        accounts = []

        for character in j['characters']:
            character_exists = False

            for account in previous_accounts:
                account_data = simplecrypt.decrypt(
                    session['password'], account.credentials
                )

                j = json.loads(account_data.decode('utf-8'))

                if j['character_id'] == character['id']:
                    flash(
                        'Character {username} has already been added, skipping'.format(
                            username=character['name']
                        )
                    )
                    character_exists = True
                    break

            if character_exists:
                continue

            creds = {'character_id': character['id'], 'refresh': refresh}

            account = Account(
                self.SITE, session['id'], character['display_name'], json.dumps(creds)
            )

            accounts.append(account)

            db.session.add(account)

        db.session.commit()

        return accounts

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        sess = cfscrape.create_scraper()

        clear_recorded_pages()

        if not isinstance(self.credentials, dict):
            raise MissingCredentials()

        character_id = self.credentials['character_id']

        req = sess.post(
            'https://beta.furrynetwork.com/api/oauth/token',
            data={
                'grant_type': 'refresh_token',
                'client_id': '123',
                'refresh_token': self.credentials['refresh'],
            },
            headers=HEADERS,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        access_token = j.get('access_token', None)
        if not access_token:
            raise BadCredentials()

        auth_headers = HEADERS.copy()
        auth_headers['Authorization'] = 'Bearer {token}'.format(token=access_token)

        req = sess.get(
            'https://beta.furrynetwork.com/api/user',
            data={'user_id': j['user_id']},
            headers=auth_headers,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        username = ''
        for character in j['characters']:
            if character['id'] == character_id:
                username = character['name']

        if username == '':
            raise SiteError(
                'Unable to find username, you may need to remove this account.'
            )

        if not submission.image_filename:
            raise SiteError('Image was missing filename')

        params = {
            'resumableChunkNumber': '1',
            'resumableChunkSize': submission.image_size,
            'resumableCurrentChunkSize': submission.image_size,
            'resumableTotalSize': submission.image_size,
            'resumableType': submission.image_mimetype,
            'resumableIdentifier': '%d-%s'
            % (submission.image_size, re.sub(r'\W+', '', submission.image_filename)),
            'resumableFilename': submission.image_filename,
            'resumableRelativePath': submission.image_filename,
            'resumableTotalChunks': '1',
        }

        req = sess.get(
            'https://beta.furrynetwork.com/api/submission/{username}/artwork/upload'.format(
                username=username
            ),
            headers=auth_headers,
            params=params,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        req = sess.post(
            'https://beta.furrynetwork.com/api/submission/{username}/artwork/upload'.format(
                username=username
            ),
            headers=auth_headers,
            params=params,
            data=submission.image_bytes,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        post_id = j.get('id')

        collection_ids = []

        if isinstance(extra, dict):
            if not self.account:
                raise MissingAccount()
            collection = extra.get('folder-{0}'.format(self.account.id))
        else:
            collection = None

        if collection and collection != 'None':
            collection_ids.append(int(collection))

        if not submission.rating:
            raise BadData()

        req = sess.patch(
            'https://beta.furrynetwork.com/api/artwork/{id}'.format(id=post_id),
            data=json.dumps(
                {
                    'rating': self.map_rating(submission.rating),
                    'description': submission.description_for_site(self.SITE),
                    'title': submission.title,
                    'tags': submission.tags,
                    'collections': collection_ids,
                    'status': 'public',
                    'publish': True,
                    'community_tags_allowed': True,
                }
            ),
            headers=auth_headers,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        if 'errors' in j:
            raise SiteError(
                'Error applying data on FurryNetwork: {err}'.format(
                    err=json.dumps(j['errors'])
                )
            )

        if not post_id:
            raise SiteError('An issue occurred when uploading')

        return 'https://beta.furrynetwork.com/artwork/{id}/'.format(id=post_id)

    def map_rating(self, rating: Rating) -> int:
        r = 2

        if rating == Rating.general:
            r = 0
        elif rating == Rating.mature:
            r = 1

        return r

    def get_folders(self, update: bool = False) -> List[Dict[str, Any]]:
        if not self.account:
            raise MissingAccount()

        prev_folders: AccountData = self.account.data.filter_by(key='folders').first()
        if prev_folders and not update:
            return prev_folders.json

        sess = cfscrape.create_scraper()

        if not self.credentials or not isinstance(self.credentials, dict):
            raise MissingCredentials()

        character_id = self.credentials['character_id']

        req = sess.post(
            'https://beta.furrynetwork.com/api/oauth/token',
            data={
                'grant_type': 'refresh_token',
                'client_id': '123',
                'refresh_token': self.credentials['refresh'],
            },
            headers=HEADERS,
        )
        req.raise_for_status()

        j = req.json()

        access_token = j.get('access_token', None)
        if not access_token:
            raise BadCredentials()

        user_id = j.get('user_id')

        auth_headers = HEADERS.copy()
        auth_headers['Authorization'] = 'Bearer {token}'.format(token=access_token)

        req = sess.get('https://beta.furrynetwork.com/api/user', headers=auth_headers)
        req.raise_for_status()
        j = req.json()

        character_name = None

        for character in j.get('characters'):
            if character.get('id') == character_id:
                character_name = character.get('name')

        req = sess.get(
            'https://beta.furrynetwork.com/api/character/{0}/artwork/collections'.format(
                character_name
            ),
            data={'user_id': user_id},
            headers=auth_headers,
        )
        req.raise_for_status()

        j = req.json()

        folders = []

        for collection in j:
            folders.append(
                {'name': collection.get('name'), 'folder_id': collection.get('id')}
            )

        if prev_folders:
            prev_folders.json = folders
        else:
            if not self.account:
                raise MissingAccount()
            prev_folders = AccountData(self.account, 'folders', folders)
            db.session.add(prev_folders)

        db.session.commit()

        return folders

    @staticmethod
    def supports_folder() -> bool:
        return True
