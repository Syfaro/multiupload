from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
import cfscrape
from flask import g, session

from multiupload.constant import HEADERS, Sites
from multiupload.models import Account, AccountData, db
from multiupload.sites import (
    AccountExists,
    BadCredentials,
    BadData,
    MissingAccount,
    Site,
    SiteError,
    SomeSubmission,
)
from multiupload.submission import Rating, Submission
from multiupload.utils import clear_recorded_pages, record_page, write_site_response

AUTH_HEADER = 'X-Weasyl-API-Key'

WHOAMI = 'https://www.weasyl.com/api/whoami'


class Weasyl(Site):
    """Weasyl."""

    SITE = Sites.Weasyl

    def parse_add_form(self, form: dict) -> dict:
        return {'token': form.get('api_token', '').strip()}

    def add_account(self, data: Optional[dict]) -> List[Account]:
        sess = cfscrape.create_scraper()

        assert data is not None

        auth_headers = HEADERS.copy()
        auth_headers[AUTH_HEADER] = data['token']

        req = sess.get(WHOAMI, headers=auth_headers)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        if 'login' not in j:
            raise BadCredentials()

        if Account.lookup_username(self.SITE, g.user.id, j['login']):
            raise AccountExists()

        account = Account(self.SITE, session['id'], j['login'], data['token'])

        db.session.add(account)
        db.session.commit()

        return [account]

    def map_rating(self, rating: Rating) -> str:
        r = '40'

        if rating == Rating.general:
            r = '10'
        elif rating == Rating.mature:
            r = '30'

        return r

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        auth_headers = HEADERS.copy()

        if not isinstance(self.credentials, bytes):
            raise BadCredentials()
        auth_headers[AUTH_HEADER] = self.credentials.decode('utf-8')

        sess = cfscrape.create_scraper()

        clear_recorded_pages()

        req = sess.get('https://www.weasyl.com/submit/visual', headers=auth_headers)
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        soup = BeautifulSoup(req.content, 'html.parser')
        try:
            token = soup.select('input[name="token"]')[0]['value']
        except ValueError:
            raise SiteError('Unable to get upload token')

        if not submission.rating:
            raise BadData()

        data = {
            'token': token,
            'title': submission.title,
            'content': submission.description_for_site(self.SITE),
            'tags': self.tag_str(submission.tags),
            'rating': self.map_rating(submission.rating),
        }

        if not isinstance(extra, dict) or not self.account:
            raise MissingAccount()

        folder = extra.get('folder-{0}'.format(self.account.id))
        if folder and folder != 'None':
            data['folderid'] = folder

        req = sess.post(
            'https://www.weasyl.com/submit/visual',
            data=data,
            files={'submitfile': submission.get_image()},
            headers=auth_headers,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)

        if req.status_code == 422:
            soup = BeautifulSoup(req.content, 'html.parser')
            try:
                message = soup.select('#error_content p')[0].get_text()
                raise SiteError(message)
            except IndexError:
                pass

        req.raise_for_status()

        return req.url

    def validate_submission(self, submission: SomeSubmission) -> List[str]:
        errors: List[str] = []

        if len(submission.tags) < 2:
            errors.append('Weasyl requires at least 2 tags')

        return errors

    def get_folders(self, update: bool = False) -> List[Dict[str, Any]]:
        if not self.account:
            raise MissingAccount()

        prev_folders: AccountData = self.account.data.filter_by(key='folders').first()
        if prev_folders and not update:
            return prev_folders.json

        auth_headers = HEADERS.copy()
        if not isinstance(self.credentials, bytes):
            raise BadCredentials()
        auth_headers[AUTH_HEADER] = self.credentials.decode('utf-8')

        sess = cfscrape.create_scraper()

        req = sess.get('https://www.weasyl.com/manage/folders', headers=auth_headers)

        soup = BeautifulSoup(req.content, 'html.parser')

        all_folders = []

        for li in soup.select('h3 + ul li a'):
            name = li.get_text()
            link = li.get('href')

            try:
                folder_id = int(link.rsplit('/', 1)[1])
            except (IndexError, ValueError):
                continue

            all_folders.append({'name': name, 'folder_id': folder_id})

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
    def supports_folder() -> bool:
        return True
