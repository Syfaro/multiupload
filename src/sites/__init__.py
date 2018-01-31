from typing import List
from typing import Union

class BadCredentials(Exception):
    pass

class AccountExists(Exception):
    pass

class Site(object):
    def pre_add_account(self) -> None:
        return None

    def add_account(self) -> None:
        raise NotImplementedError()

    def submit_artwork(self) -> None:
        raise NotImplementedError()

    def tag_str(self, tags: List[str]) -> str:
        return ' '.join(tags)
