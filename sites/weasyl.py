from flask import flash
from flask import g
from flask import session

import cfscrape
import requests

from models import db

from models import Account

from constant import Sites
from constant import HEADERS

from sites import Site
from sites import BadCredentials
from sites import AccountExists

from submission import Submission

AUTH_HEADER = 'X-Weasyl-API-Key'

WHOAMI = 'https://www.weasyl.com/api/whoami'

class Weasyl(Site):
    """Weasyl."""
    SITE = Sites.Weasyl

    def add_account(self, token, password) -> None:
        sess = cfscrape.create_scraper()

        auth_headers = HEADERS.copy()
        auth_headers[AUTH_HEADER] = token

        try:
            j = sess.get(WHOAMI, headers=auth_headers).json()

            print(j)
        except requests.RequestException:
            flash('Invalid API Token')
            raise BadCredentials()

        if 'login' not in j:
            flash('Invalid API Token')
            raise BadCredentials()

        if Account.lookup_username(self.SITE, g.user.id, j['login']):
            flash('This account has already been added.')
            raise AccountExists()

        account = Account(
            self.SITE,
            session['id'],
            j['login'],
            token,
            password
        )

        db.session.add(account)
        db.session.commit()

    def submit_artwork(self, submission: Submission) -> str:
        pass