import unittest

from multiupload.models import SavedSubmission
from multiupload.sites.sofurry import SoFurry
from multiupload.sites.weasyl import Weasyl
from multiupload.submission import Submission


class FakeImage:
    original_filename = None


class TestSiteValidations(unittest.TestCase):
    def test_tag_validation(self):
        for site in [Weasyl(), SoFurry()]:
            # check that it can correctly find tags
            for sub in [
                Submission('title', 'desc', 'tag1 tag2 tag3', 'general', FakeImage()),
                SavedSubmission(None, 'title', 'desc', 'tag1 tag2 tag3', 'general'),
            ]:
                errors = site.validate_submission(sub)
                self.assertFalse(errors)

            # check that it can also correctly find if there are no tags
            for sub in [
                Submission('title', 'desc', '', 'general', FakeImage()),
                SavedSubmission(None, 'title', 'desc', '', 'general'),
            ]:
                errors = site.validate_submission(sub)
                self.assertTrue(errors)
                self.assertIn('%s requires at least 2 tags' % site.SITE.name, errors)
