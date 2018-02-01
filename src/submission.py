from typing import List
from typing import Tuple

from enum import Enum
from io import BytesIO

from PIL import Image
from raven import breadcrumbs

from constant import Sites

from description import parse_description


def is_hashtag(tag: str) -> bool:
    """Returns if a tag is a hashtag."""
    return tag.startswith('#')


class Rating(Enum):
    """Rating is the rating for a submission."""
    general = 'general'
    mature = 'mature'
    explicit = 'explicit'


class Submission(object):
    """Submission is a normalized representation of something to post."""
    title: str = None  # Title of submission
    description: str = None  # Description of submission
    tags: List[str] = None  # Tags of submission
    hashtags: List[str] = None  # Hashtags of submission (only for Twitter)
    rating: Rating = None  # Rating of submission

    image_filename: str = None  # Filename of submission
    image_bytes: BytesIO = None  # Bytes of image in submission
    image_mimetype: str = None  # Mime type of image in submission
    _image_size: int = None

    def __init__(self, title: str, description: str, tags: str, rating: str, image):
        """Create a new Submission automatically parsing tags into regular tags
        and hashtags, and reading the image in."""
        self.title = title
        self.description = description
        self.rating = Rating[rating]

        parsed_tags = Submission.tags_from_str(tags)
        self.tags, self.hashtags = parsed_tags

        self.image_filename = image.filename
        self.image_bytes = BytesIO(image.read())  # TODO: some kind of size check?
        self.image_mimetype = image.mimetype

    def get_image(self) -> Tuple[str, BytesIO]:
        """Returns a tuple suitable for uploading."""
        return self.image_filename, self.image_bytes

    def resize_image(self, height: int, width: int) -> Tuple[str, BytesIO]:
        """Resize image to specified height and width with antialiasing"""
        image = Image.open(self.image_bytes)
        image.thumbnail((height, width), Image.ANTIALIAS)

        if image.mode != 'RGB':
            image = image.convert('RGB')  # Everything works better as RGB

        resized_image = BytesIO()
        image.save(resized_image, 'JPEG')  # TODO: should this always be JPEG?

        breadcrumbs.record(message='Resized image',
                           category='furryapp', level='info')

        return self.image_filename, resized_image

    def description_for_site(self, site: Sites) -> str:
        """Returns a formatted description for a specific site."""
        return parse_description(self.description, site.value)

    @property
    def image_size(self) -> int:
        if self._image_size:
            return self._image_size

        self._image_size = len(self.image_bytes.getbuffer())
        return self._image_size

    @staticmethod
    def tags_from_str(tags: str) -> Tuple[List[str], List[str]]:
        """Takes in a string, and returns regular keywords and hashtags."""
        tag_list = tags.split(' ')

        hashtags = []
        for keyword in tag_list:
            if keyword.startswith('#'):
                hashtags.append(keyword)

        tags_reg = list(filter(lambda x: not is_hashtag(x), tag_list))

        return tags_reg, hashtags
