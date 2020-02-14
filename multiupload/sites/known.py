from typing import Generator, List, Tuple

from multiupload.sites.deviantart import DeviantArt
from multiupload.sites.furaffinity import FurAffinity
from multiupload.sites.furrynetwork import FurryNetwork
from multiupload.sites.inkbunny import Inkbunny
from multiupload.sites.mastodon import Mastodon
from multiupload.sites.sofurry import SoFurry
from multiupload.sites.tumblr import Tumblr
from multiupload.sites.twitter import Twitter
from multiupload.sites.weasyl import Weasyl

KNOWN_SITES = [
    DeviantArt,
    FurAffinity,
    FurryNetwork,
    Inkbunny,
    Mastodon,
    SoFurry,
    Tumblr,
    Twitter,
    Weasyl,
]


def known_names() -> Generator[str, None, None]:
    """Get a list of the names of known sites."""
    for site in KNOWN_SITES:
        yield site.SITE.name


def known_list() -> List[Tuple[int, str]]:
    sites = []

    for site in KNOWN_SITES:
        sites.append((site.SITE.value, site.SITE.name))

    return sites
