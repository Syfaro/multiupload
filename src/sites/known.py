from typing import Generator
from typing import List
from typing import Tuple

from sites.weasyl import Weasyl
from sites.furaffinity import FurAffinity
from sites.twitter import Twitter
from sites.tumblr import Tumblr

KNOWN_SITES = [
    FurAffinity,
    Weasyl,
    Twitter,
    Tumblr,
]


def known_names() -> Generator[str, None, None]:
    """Get a list of the names of known sites."""
    for site in KNOWN_SITES:
        yield site.SITE.name


def known_list() -> List[Tuple[int, str]]:
    sites = []

    for site in KNOWN_SITES:
        sites.append((site.SITE.value, site.SITE.name, ))

    return sites
