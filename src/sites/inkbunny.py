from typing import Any

import json
import cfscrape

from flask import session

from constant import HEADERS
from constant import Sites

from models import Account
from models import db

from sites import BadCredentials
from sites import Site
from sites import SiteError

from submission import Rating
from submission import Submission


class Inkbunny(Site):
    """Inkbunny."""
    SITE = Sites.Inkbunny

    def __init__(self, credentials=None, account=None):
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def parse_add_form(self, form) -> dict:
        return {
            'username': form.get('username', ''),
            'password': form.get('password', ''),
        }

    def add_account(self, data: dict) -> None:
        sess = cfscrape.create_scraper()

        req = sess.post('https://inkbunny.net/api_login.php', params={
            'username': data['username'],
            'password': data['password'],
        }, headers=HEADERS)
        req.raise_for_status()

        j = req.json()

        if 'sid' not in j or j['sid'] == '':
            raise BadCredentials()

        account = Account(
            self.SITE,
            session['id'],
            data['username'],
            json.dumps({
                'username': data['username'],
                'password': data['password'],
            })
        )

        db.session.add(account)
        db.session.commit()

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        sess = cfscrape.create_scraper()

        req = sess.post('https://inkbunny.net/api_login.php', data=self.credentials, headers=HEADERS)
        req.raise_for_status()

        j = req.json()

        if 'error_message' in j:
            raise SiteError(j['error_message'])

        req = sess.post('https://inkbunny.net/api_upload.php', data={
            'sid': j['sid'],
        }, files={
            'uploadedfile[]': submission.get_image(),
        }, headers=HEADERS)
        req.raise_for_status()

        j = req.json()

        if 'submission_id' not in j:
            raise SiteError('Unable to upload')

        data = {
            'sid': j['sid'],
            'submission_id': j['submision_id'],
            'title': submission.title,
            'desc': submission.description_for_site(self.SITE),
            'keywords': submission.tags,
            'visibility': 'yes',
        }

        if submission.rating == Rating.mature:
            data['tag[2]'] = 'yes'
        elif submission.rating == Rating.explicit:
            data['tag[4]'] = 'yes'

        req = sess.post('https://inkbunny.net/api_editsubmission.php', data=data, headers=HEADERS)
        req.raise_for_status()

        j = req.json()

        if 'error_message' in j:
            raise SiteError(j['error_message'])

        return 'https://inkbunny.net/submissionview.php?id={id}'.format(id=j['submission_id'])