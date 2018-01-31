from typing import Any

from flask import session

import base64
import json
import cfscrape

from bs4 import BeautifulSoup
from PIL import Image

from models import db
from models import Account

from constant import Sites
from constant import HEADERS

from sites import Site
from sites import BadCredentials
from sites import AccountExists

from submission import Submission
from submission import Rating


class FurAffinity(Site):
    """FurAffinity."""
    SITE = Sites.FurAffinity

    def __init__(self, credentials=None):
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

        return link

    def map_rating(self, rating: Rating) -> str:
        r = '1'

        if rating == Rating.general:
            r = '0'
        elif rating == Rating.mature:
            r = '2'

        return r
