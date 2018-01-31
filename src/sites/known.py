from typing import Generator

from sites.weasyl import Weasyl
from sites.furaffinity import FurAffinity

KNOWN_SITES = [
    FurAffinity,
    Weasyl,
]


def known_names() -> Generator[str, None, None]:
    """Get a list of the names of known sites."""
    for site in KNOWN_SITES:
        yield site.SITE.name
