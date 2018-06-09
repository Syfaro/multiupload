import base64
import json
import os
import re
import time
from typing import Any

import cfscrape
from bs4 import BeautifulSoup
from flask import current_app, flash, g, session
from requests import HTTPError

from constant import HEADERS, Sites
from models import Account, AccountData, db
from sites import AccountExists, BadCredentials, Site, SiteError
from submission import Rating, Submission
from utils import write_site_response


class FurAffinity(Site):
    """FurAffinity."""

    SITE = Sites.FurAffinity

    def __init__(self, credentials=None, account=None):
        super().__init__(credentials, account)
        if credentials:
            self.credentials = json.loads(credentials)

    def pre_add_account(self) -> dict:
        sess = cfscrape.create_scraper()

        req = sess.get(
            'https://www.furaffinity.net/login/?mode=imagecaptcha', headers=HEADERS
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        session['fa_cookie_b'] = req.cookies['b']

        src = BeautifulSoup(req.content, 'html.parser').select('#captcha_img')[0]['src']

        captcha = sess.get('https://www.furaffinity.net' + src, headers=HEADERS)

        return {'captcha': base64.b64encode(captcha.content).decode('utf-8')}

    def add_account(self, data: dict) -> Account:
        sess = cfscrape.create_scraper()

        if Account.lookup_username(self.SITE, g.user.id, data['username']):
            raise AccountExists()

        req = sess.get(
            'https://www.furaffinity.net/login/?mode=imagecaptcha',
            cookies={'b': session['fa_cookie_b']},
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        req = sess.post(
            'https://www.furaffinity.net/login/',
            cookies={'b': session['fa_cookie_b']},
            data={
                'action': 'login',
                'name': data['username'],
                'pass': data['password'],
                'captcha': data['captcha'],
                'use_old_captcha': '1',
            },
            allow_redirects=False,
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        a = req.cookies.get('a', None)

        if not a:
            raise BadCredentials()

        secure_data = {'a': a, 'b': session.pop('fa_cookie_b')}

        j = json.dumps(secure_data).encode('utf-8')

        account = Account(self.SITE.value, session['id'], data['username'], j)

        db.session.add(account)
        db.session.commit()

        return account

    def parse_add_form(self, form) -> dict:
        return {
            'username': form.get('username', ''),
            'password': form.get('password', ''),
            'captcha': form.get('captcha', ''),
        }

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        sess = cfscrape.create_scraper()

        height, width = submission.image_res()
        needs_resize = height > 1280 or width > 1280

        req = sess.get(
            'https://www.furaffinity.net/submit/',
            cookies=self.credentials,
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        req = sess.post(
            'https://www.furaffinity.net/submit/',
            data={'part': '2', 'submission_type': 'submission'},
            cookies=self.credentials,
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        try:
            key = BeautifulSoup(req.content, 'html.parser').select('input[name="key"]')[
                0
            ]['value']
        except (ValueError, IndexError):
            raise SiteError('Unable to get FurAffinity upload token from part 2')

        if needs_resize:
            image = submission.resize_image(1280, 1280)
        else:
            image = submission.get_image()

        req = sess.post(
            'https://www.furaffinity.net/submit/',
            data={'part': '3', 'submission_type': 'submission', 'key': key},
            files={'submission': image},
            cookies=self.credentials,
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        page = BeautifulSoup(req.content, 'html.parser')

        try:
            key = page.select('input[name="key"]')[0]['value']
        except (ValueError, IndexError):
            text = page.select('font')
            print(text)
            with open(
                os.path.join(
                    current_app.config['DEBUG_FOLDER'],
                    '{0}.html'.format(int(time.time())),
                ),
                'wb',
            ) as f:
                f.write(req.content)
            if text:
                message = text[-1].get_text()
                print(message)
                raise SiteError('Got error: {0}'.format(message))
            raise SiteError('Unable to get FurAffinity upload token from part 3')

        data = {
            'part': '5',
            'submission_type': 'submission',
            'key': key,
            'title': submission.title,
            'message': submission.description_for_site(self.SITE),
            'keywords': self.tag_str(submission.tags),
            'rating': self.map_rating(submission.rating),
        }

        folder = extra.get('folder-{0}'.format(self.account.id))
        if folder and folder != 'None':
            data['folder_ids[]'] = folder

        req = sess.post(
            'https://www.furaffinity.net/submit/',
            data=data,
            cookies=self.credentials,
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        link = req.url

        if link == 'https://www.furaffinity.net/submit/submission/4/?msg=1':
            raise SiteError(
                'You must have a few submissions on FurAffinity before you can use this site.'
            )

        resolution = self.account['resolution_furaffinity']
        resolution = not resolution or resolution.val == 'yes'

        if needs_resize and resolution:
            match = re.search(r'view/(\d+)', link).group(1)

            req = sess.post(
                'https://www.furaffinity.net/controls/submissions/changesubmission/%s/'
                % match,
                data={'update': 'yes', 'rebuild-thumbnail': '1'},
                files={'newsubmission': submission.get_image()},
                cookies=self.credentials,
                headers=HEADERS,
            )
            write_site_response(self.SITE.value, req)

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

    def get_folders(self, update=False):
        prev_folders: AccountData = self.account.data.filter_by(key='folders').first()
        if prev_folders and not update:
            return prev_folders.json

        sess = cfscrape.create_scraper()

        req = sess.get(
            'https://www.furaffinity.net/controls/folders/submissions/',
            cookies=self.credentials,
            headers=HEADERS,
        )

        soup = BeautifulSoup(req.content, 'html.parser')

        folders = []

        for a in soup.select('table tr.folder-row a.folder-name'):
            name = a.get_text().replace('(Folder)', '').strip()

            try:
                link = a.get('href')
                match = re.search(r'/(\d+)/', link)
                folder_id = int(match.group(1))
            except (IndexError, ValueError):
                continue

            folders.append({'name': name, 'folder_id': folder_id})

        if prev_folders:
            prev_folders.json = folders
        else:
            prev_folders = AccountData(self.account, 'folders', folders)
            db.session.add(prev_folders)

        db.session.commit()

        return folders

    @staticmethod
    def supports_folder():
        return True
