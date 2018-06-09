from enum import Enum

VERSION = '0.9.0+'

HEADERS = {'User-Agent': 'Furry Multiupload %s / Syfaro <syfaro@huefox.com>' % VERSION}


class Sites(Enum):
    """IDs for the sites."""

    FurAffinity = 1
    Weasyl = 2
    FurryNetwork = 3
    Inkbunny = 4
    SoFurry = 5
    Tumblr = 7
    DeviantArt = 8
    Twitter = 100
