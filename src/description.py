import re


def parse_description(description, uploading_to):
    """Attempt to parse a description into a format valid for each site."""
    exp = r'<\|(\S+?),(\d+?),(\d)\|>'
    match = re.search(exp, description)

    runs = 0

    while match:
        if runs > 500:
            break
        runs += 1

        start, end = match.span(0)

        try:
            username = match.group(1)
            linking_to = int(match.group(2))
            link_type = int(match.group(3))
        except ValueError:
            return False

        new_text = ''

        if uploading_to == linking_to:  # Uploading to same site
            if uploading_to == 1:  # FurAffinity
                if link_type == 0:  # Just link
                    new_text = ':link%s:' % username
                elif link_type == 1:  # Just icon
                    new_text = ':%sicon:' % username
                elif link_type == 2:  # Both
                    new_text = ':icon%s:' % username
            elif uploading_to == 2:  # Weasyl
                if link_type == 0:
                    new_text = '<~%s>' % username
                elif link_type == 1:
                    new_text = '<!%s>' % username
                elif link_type == 2:
                    new_text = '<!~%s>' % username
            elif uploading_to == 3:  # FurryNetwork
                new_text = '[{0}](https://beta.furrynetwork.com/{0}/)'.format(
                    username)
            elif uploading_to == 4:
                if link_type == 0:
                    new_text = '[name]%s[/name]' % username
                elif link_type == 1:
                    new_text = '[icon]%s[/icon]' % username
                elif link_type == 2:
                    new_text = '[iconname]%s[/iconname]' % username
            elif uploading_to == 5:
                if link_type == 0:
                    clean = username.lower().replace(
                        ' ', '-').replace('_', '-')
                    new_text = '[url=https://{clean}.sofurry.com/]{username}[/url]'.format(
                        username=username, clean=clean)
                elif link_type == 1:
                    new_text = ':%sicon:' % username
                elif link_type == 2:
                    new_text = ':icon%s:' % username
            elif uploading_to == 7:
                new_text = '[{0}](https://{0}.tumblr.com/)'.format(username)
        else:  # Uploading to other site
            if uploading_to == 1:  # Uploading to FurAffinity
                if linking_to == 2:
                    new_text = '[url=https://www.weasyl.com/~{0}]{0}[/url]'.format(
                        username)
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}]{0}[/url]'.format(
                        username)
                elif linking_to == 4:
                    new_text = '[url=https://inkbunny.net/{0}]{0}[/url]'.format(
                        username)
                elif linking_to == 5:
                    clean = username.lower().replace(
                        ' ', '-').replace('_', '-')
                    new_text = '[url=https://{clean}.sofurry.com/]{username}[/url]'.format(
                        username=username, clean=clean)
                elif linking_to == 100:
                    new_text = '[url=https://twitter.com/{0}]{0}[/url]'.format(username)
                elif linking_to == 7:
                    new_text = '[url=https://{0}.tumblr.com/]{0}[/url]'.format(username)
            # Uploading to FN or Weasyl (same format type)
            elif uploading_to in (2, 3, 7):
                if linking_to == 1:
                    new_text = '[{0}](https://www.furaffinity.net/user/{0}/)'.format(
                        username)
                elif linking_to == 2:  # Weasyl
                    new_text = '[{0}](https://www.weasyl.com/~{0})'.format(
                        username)
                elif linking_to == 3:  # FurryNetwork
                    new_text = '[{0}](https://beta.furrynetwork.com/{0})'.format(
                        username)
                elif linking_to == 4:
                    new_text = '[{0}](https://inkbunny.net/{0})'.format(
                        username)
                elif linking_to == 5:
                    clean = username.lower().replace(
                        ' ', '-').replace('_', '-')
                    new_text = '[{username}](https://{clean}.sofurry.com/)'.format(
                        username=username, clean=clean)
                elif linking_to == 100:
                    new_text = '[{0}](https://twitter.com/{0})'.format(username)
                elif linking_to == 7:
                    new_text = '[{0}](https://{0}.tumblr.com/)'.format(username)
            elif uploading_to == 4:
                if linking_to == 1:
                    new_text = '[fa]%s[/fa]' % username
                elif linking_to == 2:
                    new_text = '[w]%s[/w]' % username
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}/]{0}[/url]'.format(
                        username)
                elif linking_to == 5:
                    new_text = '[sf]%s[/sf]' % username
                elif linking_to == 100:
                    new_text = '[url=https://twitter.com/{0}]{0}[/url]'.format(username)
                elif linking_to == 7:
                    new_text = '[url=https://{0}.tumblr.com/]{0}[/url]'.format(username)
            elif uploading_to == 5:
                if linking_to == 1:
                    new_text = 'fa!%s' % username
                elif linking_to == 2:
                    new_text = '[url=https://www.weasyl.com/~{0}]{0}[/url]'.format(
                        username)
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}]{0}[/url]'.format(
                        username)
                elif linking_to == 4:
                    new_text = 'ib!%s' % username
                elif linking_to == 100:
                    new_text = '[url=https://twitter.com/{0}]{0}[/url]'.format(username)
                elif linking_to == 7:
                    new_text = '[url=https://{0}.tumblr.com/]{0}[/url]'.format(username)

        description = description[0:start] + new_text + description[end:]

        match = re.search(exp, description)

    # FA, Inkbunny, and SoFurry don't support Markdown, try and convert some
    # stuff
    if uploading_to in (1, 4, 5):
        url = re.compile('\[([^\]]+)\]\(([^)"]+)(?: \"([^\"]+)\")?\)')
        match = url.search(description)

        runs = 0

        while match:
            if runs > 500:
                break
            runs += 1

            start, end = match.span(0)

            new_link = '[url={url}]{text}[/url]'.format(
                text=match.group(1), url=match.group(2))
            description = description[0:start] + new_link + description[end:]

            match = url.search(description)

    return description
