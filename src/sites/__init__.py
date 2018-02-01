from typing import List
from typing import Union
from typing import Any

from submission import Submission
from submission import Rating


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

    def add_account_callback(self, data: Any) -> Union[None, str, dict]:
        return None

    def parse_add_form(self, form) -> dict:
        raise NotImplementedError()

    def add_account(self, data: dict) -> None:
        raise NotImplementedError()

    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        raise NotImplementedError()

    def map_rating(self, rating: Rating) -> str:
        raise NotImplementedError()

    def tag_str(self, tags: List[str]) -> str:
        return ' '.join(tags)
