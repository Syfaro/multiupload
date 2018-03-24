from enum import Enum
from io import BytesIO
from os.path import join
from typing import List
from typing import Tuple

from PIL import Image
from flask import current_app
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

        if hasattr(image, 'original_filename'):
            if image.original_filename:
                self.image_filename = image.original_filename
                self.image_mimetype = image.image_mimetype
                with open(join(current_app.config['UPLOAD_FOLDER'], image.image_filename), 'rb') as f:
                    self.image_bytes = BytesIO(f.read())
        else:
            self.image_filename = image.filename
            self.image_bytes = BytesIO(image.read())
            self.image_mimetype = image.mimetype

        if self.image_bytes:
            self.image_bytes.seek(0)

    def get_image(self) -> Tuple[str, BytesIO]:
        """Returns a tuple suitable for uploading."""
        self.image_bytes.seek(0)
        return self.image_filename, self.image_bytes

    def image_res(self) -> Tuple[int, int]:
        image = Image.open(self.image_bytes)
        height, width = image.height, image.width
        self.image_bytes.seek(0)
        return height, width

    def resize_image(self, height: int, width: int, replace: bool = False) -> Tuple[str, BytesIO]:
        """Resize image to specified height and width with antialiasing"""
        image = Image.open(self.image_bytes)

        if image.height <= height and image.width <= width:
            self.image_bytes.seek(0)
            return self.image_filename, self.image_bytes

        if not image.mode.startswith('RGB'):
            image = image.convert('RGBA')  # Everything works better as RGB

        image.thumbnail((height, width), Image.ANTIALIAS)

        resized_image = BytesIO()
        image.save(resized_image, image.format)
        resized_image.seek(0)

        breadcrumbs.record(message='Resized image',
                           category='furryapp', level='info')

        if replace:
            self.image_bytes = resized_image

        self.image_bytes.seek(0)
        return self.image_filename, resized_image

    def description_for_site(self, site: Sites) -> str:
        """Returns a formatted description for a specific site."""
        return parse_description(self.description, site.value)

    @property
    def image_size(self) -> int:
        if self._image_size:
            return self._image_size

        self._image_size = len(self.image_bytes.getbuffer())
        self.image_bytes.seek(0)
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
