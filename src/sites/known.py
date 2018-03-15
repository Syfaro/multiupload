from typing import Generator
from typing import List
from typing import Tuple

from sites.furaffinity import FurAffinity
from sites.furrynetwork import FurryNetwork
from sites.inkbunny import Inkbunny
from sites.sofurry import SoFurry
from sites.tumblr import Tumblr
from sites.twitter import Twitter
from sites.weasyl import Weasyl
from sites.deviantart import DeviantArt

KNOWN_SITES = [
    FurAffinity,
    FurryNetwork,
    Inkbunny,
    SoFurry,
    Tumblr,
    Twitter,
    Weasyl,
    DeviantArt
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
