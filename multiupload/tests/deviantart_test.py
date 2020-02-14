import unittest

from multiupload.sites import SiteError
from multiupload.sites.deviantart import DeviantArt


class TestDeviantArtException(unittest.TestCase):
    def test_missing_error(self):
        resp = {}
        ret = DeviantArt._build_exception(resp)

        self.assertEqual(ret.message, 'Unknown error')
        self.assertIsInstance(ret, SiteError)

    def test_only_desc(self):
        resp = {'error_description': 'Hello, world!'}
        ret = DeviantArt._build_exception(resp)

        self.assertEqual(ret.message, 'Hello, world!')
        self.assertIsInstance(ret, SiteError)

    def test_desc_and_detail(self):
        resp = {
            'error_description': 'Hello, world!',
            'error_details': {'username': 'not good'},
        }
        ret = DeviantArt._build_exception(resp)

        self.assertEqual(ret.message, 'Hello, world!: username - not good')
        self.assertIsInstance(ret, SiteError)

    def test_desc_and_details(self):
        resp = {
            'error_description': 'Hello, world!',
            'error_details': {'username': 'not good', 'password': 'too good'},
        }
        ret = DeviantArt._build_exception(resp)

        self.assertEqual(
            ret.message, 'Hello, world!: username - not good, password - too good'
        )
        self.assertIsInstance(ret, SiteError)
