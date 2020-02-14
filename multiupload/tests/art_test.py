import unittest

from multiupload.description import get_mastodon_link, parse_description


class TestMastodonLink(unittest.TestCase):
    def test_extraction(self):
        res = get_mastodon_link('@Syfaro@foxesare.sexy')
        self.assertEqual(res, 'https://foxesare.sexy/users/Syfaro')

        res = get_mastodon_link('asdf')
        self.assertEqual(res, None)

        res = get_mastodon_link('@asdf')
        self.assertEqual(res, None)

        res = get_mastodon_link('@asdf@test')
        self.assertEqual(res, 'https://test/users/asdf')


class TestDescriptionLinks(unittest.TestCase):
    def test_single(self):
        unparsed = "[a link](https://www.google.com)"
        should_be = "[url=https://www.google.com]a link[/url]"

        self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_multiple(self):
        unparsed = (
            "[a link](https://www.google.com) with another [link](https://twitter.com)"
        )
        should_be = "[url=https://www.google.com]a link[/url] with another [url=https://twitter.com]link[/url]"

        self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_invalid(self):
        text = "[ not really a link ] (something else)"

        self.assertEqual(text, parse_description(text, 1))

    def test_no_parsing(self):
        text = "[a link](https://www.google.com)"

        self.assertEqual(text, parse_description(text, 2))


class TestDescriptionToFurAffinity(unittest.TestCase):
    def test_from_fa_link(self):
        unparsed = "<|Syfaro,1,0|>"
        should_be = ":linkSyfaro:"

        self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_from_fa_icon(self):
        unparsed = "<|Syfaro,1,1|>"
        should_be = ":Syfaroicon:"

        self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_from_fa_both(self):
        unparsed = "<|Syfaro,1,2|>"
        should_be = ":iconSyfaro:"

        self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_from_furrynetwork(self):
        should_be = "[url=https://beta.furrynetwork.com/Syfaro]Syfaro[/url]"

        for t in range(0, 2):
            unparsed = "<|Syfaro,3,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_from_inkbunny(self):
        should_be = "[url=https://inkbunny.net/Syfaro]Syfaro[/url]"

        for t in range(0, 2):
            unparsed = "<|Syfaro,4,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_from_sofurry(self):
        should_be = "[url=https://syfaro.sofurry.com/]Syfaro[/url]"

        for t in range(0, 2):
            unparsed = "<|Syfaro,5,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 1))

    def test_from_weasyl(self):
        should_be = "[url=https://www.weasyl.com/~Syfaro]Syfaro[/url]"

        for t in range(0, 2):
            unparsed = "<|Syfaro,2,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 1))


class TestDescriptionToWeasyl(unittest.TestCase):
    def test_from_weasyl_link(self):
        unparsed = "<|Syfaro,2,0|>"
        should_be = "<~Syfaro>"

        self.assertEqual(should_be, parse_description(unparsed, 2))

    def test_from_weasyl_icon(self):
        unparsed = "<|Syfaro,2,1|>"
        should_be = "<!Syfaro>"

        self.assertEqual(should_be, parse_description(unparsed, 2))

    def test_from_weasyl_both(self):
        unparsed = "<|Syfaro,2,2|>"
        should_be = "<!~Syfaro>"

        self.assertEqual(should_be, parse_description(unparsed, 2))

    def test_from_furaffinity(self):
        should_be = "<fa:Syfaro>"

        for t in range(0, 2):
            unparsed = "<|Syfaro,1,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 2))

    def test_from_furrynetwork(self):
        should_be = "[Syfaro](https://beta.furrynetwork.com/Syfaro)"

        for t in range(0, 2):
            unparsed = "<|Syfaro,3,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 2))

    def test_from_inkbunny(self):
        should_be = "<ib:Syfaro>"

        for t in range(0, 2):
            unparsed = "<|Syfaro,4,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 2))

    def test_from_sofurry(self):
        should_be = "<sf:Syfaro>"

        for t in range(0, 2):
            unparsed = "<|Syfaro,5,%d|>" % t

            self.assertEqual(should_be, parse_description(unparsed, 2))
