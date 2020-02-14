from io import BytesIO
from os.path import join
from typing import Any, List, Union, Optional

from flask import current_app
from werkzeug import Response
from PIL import Image

from models import Account, SavedSubmission, SubmissionGroup
from submission import Rating, Submission


SomeSubmission = Union[Submission, SavedSubmission]


class BadCredentials(Exception):
    pass


class AccountExists(Exception):
    pass


class SiteError(Exception):
    def __init__(self, message: str):
        self.message = message


class Site(object):
    credentials: Union[None, str, dict] = None
    account: Optional[Account] = None

    def __init__(self, credentials=None, account=None):
        self.credentials = credentials
        self.account = account

    def pre_add_account(self) -> Optional[Union[dict, Response]]:
        return None

    def add_account_callback(self) -> Union[None, str, dict]:
        return None

    def parse_add_form(self, form) -> Optional[dict]:
        return None

    def add_account(self, data: dict) -> Union[Account, List[Account]]:
        raise NotImplementedError()

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        raise NotImplementedError()

    def map_rating(self, rating: Rating) -> Optional[Any]:
        return None

    def validate_submission(self, submission: SomeSubmission) -> List[str]:
        return []

    def tag_str(self, tags: List[str]) -> str:
        return ' '.join(tags)

    def get_folders(self, update=False) -> Optional[List[dict]]:
        return None

    def upload_group(self, group: SubmissionGroup, extra: Any = None):
        raise NotImplementedError()

    @staticmethod
    def supports_group() -> bool:
        return False

    @staticmethod
    def supports_folder() -> bool:
        return False

    @staticmethod
    def collect_images(submissions: List[SavedSubmission], max_size=None, format=None):
        for sub in submissions:
            with open(
                join(current_app.config['UPLOAD_FOLDER'], sub.image_filename), 'rb'
            ) as f:
                image_bytes = BytesIO(f.read())

            if max_size:
                image = Image.open(image_bytes)
                if not image.mode.startswith('RGB'):
                    image = image.convert('RGBA')
                image.thumbnail((max_size, max_size), Image.ANTIALIAS)
                image_bytes = BytesIO()
                if format:
                    image.save(image_bytes, format)
                else:
                    image.save(image_bytes, image.format)
                image_bytes.seek(0)

            yield {
                'filename': sub.image_filename,
                'original_filename': sub.original_filename,
                'mimetype': sub.image_mimetype,
                'bytes': image_bytes,
            }
