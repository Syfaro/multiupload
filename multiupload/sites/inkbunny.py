import json
from typing import Any, Optional, List

import cfscrape
from flask import session

from multiupload.constant import HEADERS, Sites
from multiupload.models import Account, SubmissionGroup, db
from multiupload.sites import BadCredentials, Site, SiteError
from multiupload.submission import Rating, Submission
from multiupload.utils import write_site_response, record_page, clear_recorded_pages


class Inkbunny(Site):
    """Inkbunny."""

    SITE = Sites.Inkbunny

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
            'https://inkbunny.net/api_login.php',
            params={'username': data['username'], 'password': data['password']},
            headers=HEADERS,
        )
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        if 'sid' not in j or j['sid'] == '':
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

        req = sess.post(
            'https://inkbunny.net/api_login.php', data=self.credentials, headers=HEADERS
        )
        record_page(req)
        req.raise_for_status()

        j = req.json()

        if 'error_message' in j:
            raise SiteError(j['error_message'])

        req = sess.post(
            'https://inkbunny.net/api_upload.php',
            data={'sid': j['sid']},
            files={'uploadedfile[]': submission.get_image()},
            headers=HEADERS,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        if 'submission_id' not in j:
            raise SiteError('Unable to upload')

        data = {
            'sid': j['sid'],
            'submission_id': j['submission_id'],
            'title': submission.title,
            'desc': submission.description_for_site(self.SITE),
            'keywords': self.tag_str(submission.tags),
            'visibility': 'yes',
        }

        if submission.rating == Rating.mature:
            data['tag[2]'] = 'yes'
        elif submission.rating == Rating.explicit:
            data['tag[4]'] = 'yes'

        req = sess.post(
            'https://inkbunny.net/api_editsubmission.php', data=data, headers=HEADERS
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        if 'error_message' in j:
            raise SiteError(j['error_message'])

        return 'https://inkbunny.net/submissionview.php?id={id}'.format(
            id=j['submission_id']
        )

    def upload_group(self, group: SubmissionGroup, extra: Any = None) -> str:
        sess = cfscrape.create_scraper()

        clear_recorded_pages()

        req = sess.post(
            'https://inkbunny.net/api_login.php', data=self.credentials, headers=HEADERS
        )
        req.raise_for_status()

        j = req.json()

        if 'error_message' in j:
            raise SiteError(j['error_message'])

        master = group.master
        s = master.submission
        submissions = group.submissions

        images = [
            ('uploadedfile[]', (image.original_filename, image.data, image.mimetype))
            for image in self.collect_images(submissions)
        ]

        req = sess.post(
            'https://inkbunny.net/api_upload.php',
            data={'sid': j['sid']},
            files=images,
            headers=HEADERS,
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        if 'submission_id' not in j:
            raise SiteError('Unable to upload')

        data = {
            'sid': j['sid'],
            'submission_id': j['submission_id'],
            'title': master.title,
            'desc': s.description_for_site(self.SITE),
            'keywords': self.tag_str(master.tags),
            'visibility': 'yes',
        }

        if master.rating == Rating.mature:
            data['tag[2]'] = 'yes'
        elif master.rating == Rating.explicit:
            data['tag[4]'] = 'yes'

        req = sess.post(
            'https://inkbunny.net/api_editsubmission.php', data=data, headers=HEADERS
        )
        record_page(req)
        write_site_response(self.SITE.value, req)
        req.raise_for_status()

        j = req.json()

        if 'error_message' in j:
            raise SiteError(j['error_message'])

        return 'https://inkbunny.net/submissionview.php?id={id}'.format(
            id=j['submission_id']
        )

    @staticmethod
    def supports_group() -> bool:
        return True
