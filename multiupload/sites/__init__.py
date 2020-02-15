from io import BytesIO
from os.path import join
from typing import Any, List, Union, Optional, Generator, Dict
from abc import ABCMeta
from dataclasses import dataclass

from flask import current_app
from werkzeug import Response, ImmutableMultiDict
from PIL import Image

from multiupload.models import Account, SavedSubmission, SubmissionGroup
from multiupload.submission import Rating, Submission
from multiupload.constant import Sites


SomeSubmission = Union[Submission, SavedSubmission]
Credentials = Optional[Union[str, dict]]


class BadCredentials(Exception):
    pass


class AccountExists(Exception):
    pass


class SiteError(Exception):
    def __init__(self, message: str):
        self.message = message


class MissingAccount(Exception):
    pass


class MissingCredentials(Exception):
    pass


class BadData(Exception):
    pass


@dataclass
class CollectedImage:
    filename: str
    original_filename: str
    mimetype: str
    data: BytesIO


class Site(metaclass=ABCMeta):
    SITE: Sites

    credentials: Credentials
    account: Optional[Account]

    def __init__(
        self, credentials: Optional[str] = None, account: Optional[Account] = None
    ) -> None:
        self.credentials = credentials
        self.account = account

    def pre_add_account(self) -> Optional[Union[Dict[str, Any], Response]]:
        """Run a function before prompting the user to add an account on this
        site. It can be used to add data to the site's template or to redirect
        to a site-specific login page.
        """
        return None

    def add_account_callback(self) -> Optional[Union[str, dict, Response]]:
        return None

    def parse_add_form(self, form: ImmutableMultiDict) -> Optional[Dict[str, Any]]:
        """Extract data from a form into your own dict."""
        return None

    def add_account(self, data: Dict[str, Any]) -> List[Account]:
        """Add a new account from your data extracted with parse_add_form.

        Always returned as a list for sites that can add multiple accounts for
        one credential set.
        """
        raise NotImplementedError()

    # TODO: rename maybe? doesn't fit with upload_group
    def submit_artwork(self, submission: Submission, extra: Any = None) -> str:
        """Submit artwork to the site with extra data, returning a link to
        the posted submission.
        """
        raise NotImplementedError()

    # TODO: should this be a required return value?
    def map_rating(self, rating: Rating) -> Optional[Any]:
        """Map a Rating into a site-specific value."""
        return None

    def validate_submission(self, submission: SomeSubmission) -> List[str]:
        """Get validation errors from a submission. Called before any uploads,
        useful to make sure all data is correct before attempting anything.
        """
        return []

    def tag_str(self, tags: List[str]) -> str:
        """Convert a list of tags into a string for the site.

        Most sites prefer space separated tags, but a few require comma
        separated values."""
        return ' '.join(tags)

    # TODO: should this be a required return value? it's gated by supports_folders
    def get_folders(self, update: bool = False) -> Optional[List[dict]]:
        """Get folders from this site.

        If update is False, use cached data about folders available."""
        return None

    def upload_group(self, group: SubmissionGroup, extra: Any = None) -> str:
        """Upload a group of submissions to this site.

        Gated by supports_group, returns a link to the created submission."""
        raise NotImplementedError()

    @staticmethod
    def supports_group() -> bool:
        """If the site supports group uploads.

        If it returns True, upload_group will be called for group uploads. If
        not, submit_artwork will be called for each item in the group.
        """
        return False

    @staticmethod
    def supports_folder() -> bool:
        """If the site supports folders.

        Used for feature display mostly, also used to gate calling get_folders
        when a folder refresh is requested.
        """
        return False

    @staticmethod
    def collect_images(
        submissions: List[SavedSubmission],
        max_size: Optional[int] = None,
        format: str = None,
    ) -> Generator[CollectedImage, None, None]:
        """Collect all images from a list of saved submissions.

        Used for uploading groups which store images in multiple submissions
        internally, which get aggregated into a single post."""
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

            yield CollectedImage(
                filename=sub.image_filename,
                original_filename=sub.original_filename,
                mimetype=sub.image_mimetype,
                data=image_bytes,
            )
