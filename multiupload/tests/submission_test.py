import unittest

from multiupload.submission import Submission


class TestTagParsing(unittest.TestCase):
    TAGS_NO_COMMA = 'hello world #test extra tag'
    TAGS_WITH_COMMA = 'hello, world, #test, extra tag'

    def test_tag_nocommas(self):
        keywords, hashtags = Submission.tags_from_str(self.TAGS_NO_COMMA)

        self.assertListEqual(keywords, ['hello', 'world', 'extra', 'tag'])
        self.assertListEqual(hashtags, ['#test'])

    def test_tag_commas(self):
        keywords, hashtags = Submission.tags_from_str(self.TAGS_WITH_COMMA)

        self.assertListEqual(keywords, ['hello', 'world', 'extra tag'])
        self.assertListEqual(hashtags, ['#test'])
