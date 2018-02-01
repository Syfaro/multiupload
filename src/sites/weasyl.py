from typing import Any

import cfscrape
from bs4 import BeautifulSoup

from flask import g
from flask import session

from constant import HEADERS
from constant import Sites

from models import Account
from models import db

from sites import AccountExists
from sites import BadCredentials
from sites import Site

from submission import Rating
from submission import Submission

AUTH_HEADER = 'X-Weasyl-API-Key'

WHOAMI = 'https://www.weasyl.com/api/whoami'


class Weasyl(Site):
    """Weasyl."""
    SITE = Sites.Weasyl

    def parse_add_form(self, form) -> dict:
        return {
            'token': form.get('api_token', '').strip(),
        }

    def add_account(self, data: dict) -> None:
        sess = cfscrape.create_scraper()

        auth_headers = HEADERS.copy()
        auth_headers[AUTH_HEADER] = data['token']

        req = sess.get(WHOAMI, headers=auth_headers)
        req.raise_for_status()

        j = req.json()

        if 'login' not in j:
            raise BadCredentials()

        if Account.lookup_username(self.SITE, g.user.id, j['login']):
            raise AccountExists()

        account = Account(
            self.SITE,
            session['id'],
            j['login'],
            data['token'],
        )

        db.session.add(account)
        db.session.commit()

    def map_rating(self, rating: Rating) -> str:
        r = '40'

        if rating == Rating.general:
            r = '10'
        elif rating == Rating.mature:
            r = '30'

        return r

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        auth_headers = HEADERS.copy()
        auth_headers[AUTH_HEADER] = self.credentials

        sess = cfscrape.create_scraper()

        req = sess.get('https://www.weasyl.com/submit/visual', headers=auth_headers)
        req.raise_for_status()

        soup = BeautifulSoup(req.content, 'html.parser')
        token = soup.select('input[name="token"]')[0]['value']

        req = sess.post('https://www.weasyl.com/submit/visual', data={
            'token': token,
            'title': submission.title,
            'content': submission.description_for_site(self.SITE),
            'tags': self.tag_str(submission.tags),
            'rating': self.map_rating(submission.rating)
        }, files={
            'submitfile': submission.get_image(),
        }, headers=auth_headers)
        req.raise_for_status()

        return req.url
