import json
from typing import Any, List, Optional

import cfscrape
from bs4 import BeautifulSoup
from flask import session

from multiupload.constant import HEADERS, Sites
from multiupload.models import Account, db
from multiupload.sites import (
    BadCredentials,
    BadData,
    Site,
    SiteError,
    MissingAccount,
    MissingCredentials,
)
from multiupload.submission import Rating, Submission
from multiupload.utils import write_site_response, record_page, clear_recorded_pages


class SoFurry(Site):
    SITE = Sites.SoFurry

    def __init__(
        self, credentials: Optional[str] = None, account: Optional[Account] = None
    ) -> None:
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def parse_add_form(self, form: dict) -> dict:
        return {
            'username': form.get('username', ''),
            'password': form.get('password', ''),
        }

    def add_account(self, data: dict) -> List[Account]:
        sess = cfscrape.create_scraper()

        req = sess.post(
            'https://www.sofurry.com/user/login',
            data={
                'LoginForm[sfLoginUsername]': data['username'],
                'LoginForm[sfLoginPassword]': data['password'],
            },
            headers=HEADERS,
            allow_redirects=False,
        )
        write_site_response(self.SITE.value, req)

        if 'sfuser' not in req.cookies:
            raise BadCredentials()

        account = Account(
            self.SITE,
            session['id'],
            data['username'],
            json.dumps({'username': data['username'], 'password': data['password']}),
        )

        db.session.add(account)
        db.session.commit()

        return [account]

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        sess = cfscrape.create_scraper()

        clear_recorded_pages()

        if not isinstance(self.credentials, dict):
            raise MissingCredentials()

        if not isinstance(extra, dict):
            raise BadData()

        req = sess.post(
            'https://www.sofurry.com/user/login',
            data={
                'LoginForm[sfLoginUsername]': self.credentials['username'],
                'LoginForm[sfLoginPassword]': self.credentials['password'],
            },
            headers=HEADERS,
            allow_redirects=False,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)

        if 'sfuser' not in req.cookies:
            raise BadCredentials()

        req = sess.get(
            'https://www.sofurry.com/upload/details?contentType=1', headers=HEADERS
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        soup = BeautifulSoup(req.content, 'html.parser')
        try:
            key = soup.select('input[name="YII_CSRF_TOKEN"]')[0]['value']
            key2 = soup.select('#UploadForm_P_id')[0]['value']
        except (IndexError, ValueError):
            raise SiteError('Unable to load upload page for SoFurry')

        if not submission.rating:
            raise BadData()

        req = sess.post(
            'https://www.sofurry.com/upload/details?contentType=1',
            data={
                'UploadForm[P_title]': submission.title,
                'UploadForm[contentLevel]': self.map_rating(submission.rating),
                'UploadForm[description]': submission.description_for_site(self.SITE),
                'UploadForm[formtags]': self.tag_str(submission.tags),
                'YII_CSRF_TOKEN': key,
                'UploadForm[P_id]': key2,
            },
            files={'UploadForm[binarycontent]': submission.get_image()},
            headers=HEADERS,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        return req.url

    def map_rating(self, rating: Rating) -> str:
        r = '2'

        if not self.account:
            raise MissingAccount()

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

    def validate_submission(self, submission: Submission) -> List[str]:
        errors: List[str] = []

        if len(submission.tags) < 2:
            errors.append('SoFurry requires at least 2 tags')

        return errors
