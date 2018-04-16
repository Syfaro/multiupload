from io import BytesIO
from typing import Any
from typing import List
from typing import Union

from flask import current_app
from os.path import join

from models import Account, SavedSubmission, SubmissionGroup
from submission import Rating
from submission import Submission


class BadCredentials(Exception):
    pass


class AccountExists(Exception):
    pass


class SiteError(Exception):
    def __init__(self, message: str):
        self.message = message


class Site(object):
    credentials: Union[None, str, dict] = None

    def __init__(self, credentials=None, account=None):
        self.credentials = credentials
        self.account = account

    def pre_add_account(self) -> Union[None, dict]:
        return None

    def add_account_callback(self) -> Union[None, str, dict]:
        return None

    def parse_add_form(self, form) -> Union[None, dict]:
        return None

    def add_account(self, data: dict) -> Union[Account, List[Account]]:
        raise NotImplementedError()

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        raise NotImplementedError()

    def map_rating(self, rating: Rating) -> Union[None, str]:
        return None

    def validate_submission(self, submission: Submission) -> Union[None, List[str]]:
        return None

    def tag_str(self, tags: List[str]) -> str:
        return ' '.join(tags)

    def get_folders(self, update=False) -> Union[None, List[dict]]:
        return None

    def upload_group(self, group: SubmissionGroup):
        raise NotImplementedError()

    @staticmethod
    def supports_group() -> bool:
        return False

    @staticmethod
    def collect_images(submissions: List[SavedSubmission]):
        for sub in submissions:
            with open(join(current_app.config['UPLOAD_FOLDER'], sub.image_filename), 'rb') as f:
                image_bytes = BytesIO(f.read())

            yield {
                'filename': sub.image_filename,
                'original_filename': sub.original_filename,
                'mimetype': sub.image_mimetype,
                'bytes': image_bytes,
            }
