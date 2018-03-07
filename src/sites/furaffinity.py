from typing import Any

import base64
import json
import re
import cfscrape

from PIL import Image
from bs4 import BeautifulSoup
from requests import HTTPError

from flask import flash
from flask import g
from flask import session

from constant import HEADERS
from constant import Sites

from models import Account
from models import db

from sites import AccountExists
from sites import BadCredentials
from sites import Site
from sites import SiteError

from submission import Rating
from submission import Submission


class FurAffinity(Site):
    """FurAffinity."""
    SITE = Sites.FurAffinity

    def __init__(self, credentials=None, account=None):
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def pre_add_account(self) -> dict:
        sess = cfscrape.create_scraper()

        req = sess.get('https://www.furaffinity.net/login/?mode=imagecaptcha', headers=HEADERS)
        req.raise_for_status()

        session['fa_cookie_b'] = req.cookies['b']

        src = BeautifulSoup(req.content, 'html.parser').select('#captcha_img')[0]['src']

        captcha = sess.get('https://www.furaffinity.net' + src, headers=HEADERS)

        return {
            'captcha': base64.b64encode(captcha.content).decode('utf-8')
        }

    def add_account(self, data: dict) -> None:
        sess = cfscrape.create_scraper()

        if Account.lookup_username(self.SITE, g.user.id, data['username']):
            raise AccountExists()

        req = sess.get('https://www.furaffinity.net/login/?mode=imagecaptcha', cookies={
            'b': session['fa_cookie_b'],
        }, headers=HEADERS)
        req.raise_for_status()

        req = sess.post('https://www.furaffinity.net/login/', cookies={
            'b': session['fa_cookie_b'],
        }, data={
            'action': 'login',
            'name': data['username'],
            'pass': data['password'],
            'captcha': data['captcha'],
            'use_old_captcha': '1',
        }, allow_redirects=False, headers=HEADERS)
        req.raise_for_status()

        a = req.cookies.get('a', None)

        if not a:
            raise BadCredentials()

        secure_data = {
            'a': a,
            'b': session.pop('fa_cookie_b'),
        }

        j = json.dumps(secure_data).encode('utf-8')

        account = Account(
            self.SITE.value,
            session['id'],
            data['username'],
            j
        )

        db.session.add(account)
        db.session.commit()

    def parse_add_form(self, form) -> dict:
        return {
            'username': form.get('username', ''),
            'password': form.get('password', ''),
            'captcha': form.get('captcha', ''),
        }

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        sess = cfscrape.create_scraper()

        image = Image.open(submission.image_bytes)
        height, width = image.size

        needs_resize = height > 1280 or width > 1280

        req = sess.get('https://www.furaffinity.net/submit/', cookies=self.credentials, headers=HEADERS)
        req.raise_for_status()

        req = sess.post('https://www.furaffinity.net/submit/', data={
            'part': '2',
            'submission_type': 'submission',
        }, cookies=self.credentials, headers=HEADERS)
        req.raise_for_status()

        key = BeautifulSoup(req.content, 'html.parser').select('input[name="key"]')[0]['value']

        if needs_resize:
            image = submission.resize_image(1280, 1280)
        else:
            image = submission.get_image()

        req = sess.post('https://www.furaffinity.net/submit/', data={
            'part': '3',
            'submission_type': 'submission',
            'key': key,
        }, files={
            'submission': image,
        }, cookies=self.credentials, headers=HEADERS)
        req.raise_for_status()

        key = BeautifulSoup(req.content, 'html.parser').select('input[name="key"]')[0]['value']

        req = sess.post('https://www.furaffinity.net/submit/', data={
            'part': '5',
            'submission_type': 'submission',
            'key': key,
            'title': submission.title,
            'message': submission.description_for_site(self.SITE),
            'keywords': self.tag_str(submission.tags),
            'rating': self.map_rating(submission.rating),
        }, cookies=self.credentials, headers=HEADERS)
        req.raise_for_status()

        link = req.url

        if link == 'https://www.furaffinity.net/submit/submission/4/?msg=1':
            raise SiteError('You must have a few submissions on FurAffinity before you can use this site.')

        resolution = self.account['resolution_furaffinity']
        resolution = not resolution or resolution.val == 'yes'

        if needs_resize and resolution:
            match = re.search(r'view/(\d+)', link).group(1)

            req = sess.post('https://www.furaffinity.net/controls/submissions/changesubmission/%s/' % match, data={
                'update': 'yes',
                'rebuild-thumbnail': '1',
            }, files={
                'newsubmission': submission.get_image(),
            }, cookies=self.credentials, headers=HEADERS)

            try:
                req.raise_for_status()
            except HTTPError:
                flash('Unable to increase resolution on FurAffinity submission.')

        return link

    def map_rating(self, rating: Rating) -> str:
        r = '1'

        if rating == Rating.general:
            r = '0'
        elif rating == Rating.mature:
            r = '2'

        return r
