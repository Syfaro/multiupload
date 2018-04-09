import json
from typing import Any
from typing import List
from typing import Union

import cfscrape
from bs4 import BeautifulSoup
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


class SoFurry(Site):
    SITE = Sites.SoFurry

    def __init__(self, credentials=None, account=None):
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def parse_add_form(self, form) -> dict:
        return {
            'username': form.get('username', ''),
            'password': form.get('password', ''),
        }

    def add_account(self, data: dict) -> Account:
        sess = cfscrape.create_scraper()

        req = sess.post('https://www.sofurry.com/user/login', data={
            'LoginForm[sfLoginUsername]': data['username'],
            'LoginForm[sfLoginPassword]': data['password'],
        }, headers=HEADERS, allow_redirects=False)

        if 'sfuser' not in req.cookies:
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

        return account

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        sess = cfscrape.create_scraper()

        req = sess.post('https://www.sofurry.com/user/login', data={
            'LoginForm[sfLoginUsername]': self.credentials['username'],
            'LoginForm[sfLoginPassword]': self.credentials['password'],
        }, headers=HEADERS, allow_redirects=False)

        if 'sfuser' not in req.cookies:
            raise BadCredentials()

        req = sess.get('https://www.sofurry.com/upload/details?contentType=1', headers=HEADERS)
        req.raise_for_status()

        soup = BeautifulSoup(req.content, 'html.parser')
        try:
            key = soup.select('input[name="YII_CSRF_TOKEN"]')[0]['value']
            key2 = soup.select('#UploadForm_P_id')[0]['value']
        except ValueError:
            raise SiteError('Unable to load upload page')

        req = sess.post('https://www.sofurry.com/upload/details?contentType=1', data={
            'UploadForm[P_title]': submission.title,
            'UploadForm[contentLevel]': self.map_rating(submission.rating),
            'UploadForm[description]': submission.description_for_site(self.SITE),
            'UploadForm[formtags]': self.tag_str(submission.tags),
            'YII_CSRF_TOKEN': key,
            'UploadForm[P_id]': key2,
        }, files={
            'UploadForm[binarycontent]': submission.get_image(),
        }, headers=HEADERS)
        req.raise_for_status()

        return req.url

    def map_rating(self, rating: Rating) -> str:
        r = '2'

        should_remap = self.account['remap_sofurry']
        if should_remap and should_remap.val == 'yes':
            if rating == Rating.general:
                r = '0'
            elif rating == Rating.mature:
                r = '1'
        else:
            if rating == Rating.general:
                r = '0'
            elif rating == Rating.mature or rating == Rating.explicit:
                r = '1'

        return r

    def tag_str(self, tags: List[str]) -> str:
        return ', '.join(tags)

    def validate_submission(self, submission: Submission) -> Union[None, List[str]]:
        if len(submission.tags) < 2:
            return ['SoFurry requires at least two tags.']

        return None
