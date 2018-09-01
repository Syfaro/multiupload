import re


def get_mastodon_link(username) -> str:
    handle, domain = username.rsplit('@', 1)
    return 'https://{domain}/users/{handle}'.format(domain=domain, handle=handle.strip('@'))


def parse_description(description, uploading_to) -> str:
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

        masto_link = get_mastodon_link(username)

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
                new_text = '[{0}](https://beta.furrynetwork.com/{0}/)'.format(username)
            elif uploading_to == 4:
                if link_type == 0:
                    new_text = '[name]%s[/name]' % username
                elif link_type == 1:
                    new_text = '[icon]%s[/icon]' % username
                elif link_type == 2:
                    new_text = '[iconname]%s[/iconname]' % username
            elif uploading_to == 5:
                if link_type == 0:
                    clean = username.lower().replace(' ', '-').replace('_', '-')
                    new_text = '[url=https://{clean}.sofurry.com/]{username}[/url]'.format(
                        username=username, clean=clean
                    )
                elif link_type == 1:
                    new_text = ':%sicon:' % username
                elif link_type == 2:
                    new_text = ':icon%s:' % username
            elif uploading_to == 7:
                new_text = '[{0}](https://{0}.tumblr.com/)'.format(username)
            elif uploading_to == 8:
                if link_type == 0:
                    new_text = ':dev{0}:'.format(username)
                else:
                    new_text = ':icon{0}:'.format(username)
        else:  # Uploading to other site
            if uploading_to == 1:  # Uploading to FurAffinity
                if linking_to == 2:
                    new_text = '[url=https://www.weasyl.com/~{0}]{0}[/url]'.format(
                        username
                    )
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}]{0}[/url]'.format(
                        username
                    )
                elif linking_to == 4:
                    new_text = '[url=https://inkbunny.net/{0}]{0}[/url]'.format(
                        username
                    )
                elif linking_to == 5:
                    clean = username.lower().replace(' ', '-').replace('_', '-')
                    new_text = '[url=https://{clean}.sofurry.com/]{username}[/url]'.format(
                        username=username, clean=clean
                    )
                elif linking_to == 100:
                    new_text = '[url=https://twitter.com/{0}]{0}[/url]'.format(username)
                elif linking_to == 101:
                    new_text = '[url={0}]{1}[/url]'.format(masto_link, username)
                elif linking_to == 7:
                    new_text = '[url=https://{0}.tumblr.com/]{0}[/url]'.format(username)
                elif linking_to == 8:
                    new_text = '[url=https://{0}.deviantart.com/]{1}[/url]'.format(
                        username.lower(), username
                    )
            elif uploading_to == 2:
                if linking_to == 1:
                    new_text = '<fa:{0}>'.format(username)
                elif linking_to == 3:  # FurryNetwork
                    new_text = '[{0}](https://beta.furrynetwork.com/{0})'.format(
                        username
                    )
                elif linking_to == 4:
                    new_text = '<ib:{0}>'.format(username)
                elif linking_to == 5:
                    new_text = '<sf:{0}>'.format(username)
                elif linking_to == 100:
                    new_text = '[{0}](https://twitter.com/{0})'.format(username)
                elif linking_to == 101:
                    new_text = '[{0}]({1})'.format(username, masto_link)
                elif linking_to == 7:
                    new_text = '[{0}](https://{1}.tumblr.com/)'.format(
                        username, username.lower()
                    )
                elif linking_to == 8:
                    new_text = '<da:{0}>'.format(username)
            elif uploading_to in (3, 7):
                if linking_to == 1:
                    new_text = '[{0}](https://www.furaffinity.net/user/{0}/)'.format(
                        username
                    )
                elif linking_to == 2:  # Weasyl
                    new_text = '[{0}](https://www.weasyl.com/~{0})'.format(username)
                elif linking_to == 3:  # FurryNetwork
                    new_text = '[{0}](https://beta.furrynetwork.com/{0})'.format(
                        username
                    )
                elif linking_to == 4:
                    new_text = '[{0}](https://inkbunny.net/{0})'.format(username)
                elif linking_to == 5:
                    clean = username.lower().replace(' ', '-').replace('_', '-')
                    new_text = '[{username}](https://{clean}.sofurry.com/)'.format(
                        username=username, clean=clean
                    )
                elif linking_to == 100:
                    new_text = '[{0}](https://twitter.com/{0})'.format(username)
                elif linking_to == 101:
                    new_text = '[{0}]({1})'.format(username, masto_link)
                elif linking_to == 7:
                    new_text = '[{0}](https://{0}.tumblr.com/)'.format(username)
                elif linking_to == 8:
                    new_text = '[{1}](https://{0}.deviantart.com/)'.format(
                        username.lower(), username
                    )
            elif uploading_to == 4:
                if linking_to == 1:
                    new_text = '[fa]%s[/fa]' % username
                elif linking_to == 2:
                    new_text = '[w]%s[/w]' % username
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}/]{0}[/url]'.format(
                        username
                    )
                elif linking_to == 5:
                    new_text = '[sf]%s[/sf]' % username
                elif linking_to == 100:
                    new_text = '[url=https://twitter.com/{0}]{0}[/url]'.format(username)
                elif linking_to == 101:
                    new_text = '[url={0}]{1}[/url]'.format(masto_link, username)
                elif linking_to == 7:
                    new_text = '[url=https://{0}.tumblr.com/]{0}[/url]'.format(username)
                elif linking_to == 8:
                    new_text = '[da]{0}[/da]'.format(username)
            elif uploading_to == 5:
                if linking_to == 1:
                    new_text = 'fa!%s' % username
                elif linking_to == 2:
                    new_text = '[url=https://www.weasyl.com/~{0}]{0}[/url]'.format(
                        username
                    )
                elif linking_to == 3:
                    new_text = '[url=https://beta.furrynetwork.com/{0}]{0}[/url]'.format(
                        username
                    )
                elif linking_to == 4:
                    new_text = 'ib!%s' % username
                elif linking_to == 100:
                    new_text = '[url=https://twitter.com/{0}]{0}[/url]'.format(username)
                elif linking_to == 101:
                    new_text = '[url={0}]{1}[/url]'.format(masto_link, username)
                elif linking_to == 7:
                    new_text = '[url=https://{0}.tumblr.com/]{0}[/url]'.format(username)
                elif linking_to == 8:
                    new_text = '[url=https://{0}.deviantart.com/]{1}[/url]'.format(
                        username.lower(), username
                    )
            elif uploading_to == 8:
                if linking_to == 1:
                    new_text = '<a href="https://www.furaffinity.net/user/{0}">{0}</a>'.format(
                        username
                    )
                elif linking_to == 2:
                    new_text = '<a href="https://www.weasyl.com/~{0}">{0}</a>'.format(
                        username
                    )
                elif linking_to == 3:
                    new_text = '<a href="https://beta.furrynetwork.com/{0}">{0}</a>'.format(
                        username
                    )
                elif linking_to == 4:
                    new_text = '<a href="https://inkbunny.net/{0}">{0}</a>'.format(
                        username
                    )
                elif linking_to == 5:
                    clean = username.lower().replace(' ', '-').replace('_', '-')
                    new_text = '<a href="https://{clean}.sofurry.com/">{username}</a>'.format(
                        username=username, clean=clean
                    )
                elif linking_to == 7:
                    new_text = '<a href="https://{1}.tumblr.com/">{0}</a>'.format(
                        username, username.lower()
                    )

        description = description[0:start] + new_text + description[end:]

        match = re.search(exp, description)

    # Various sites don't support Markdown, try and convert some stuff
    if uploading_to in (1, 4, 5, 8):
        url = re.compile('\[([^\]]+)\]\(([^)"]+)(?: \"([^\"]+)\")?\)')
        match = url.search(description)

        runs = 0

        while match:
            if runs > 500:
                break
            runs += 1

            start, end = match.span(0)

            if uploading_to == 8:  # DeviantArt uses HTML
                new_link = '<a href="{url}">{text}</a>'
            else:
                new_link = '[url={url}]{text}[/url]'

            new_link = new_link.format(text=match.group(1), url=match.group(2))

            description = description[0:start] + new_link + description[end:]

            match = url.search(description)

        if uploading_to == 8:
            description = re.sub(
                r'([*_]{2})(.+)\1', r'<strong>\2</strong>', description
            )  # strong
            description = re.sub(r'([*_])(.+)\1', r'<em>\2</em>', description)  # italic
            description = re.sub(
                r'(~{2})(.+)\1', r'<strike>\2</strike>', description
            )  # strikethrough
            description = re.sub(r'`(.+)`', r'\1', description)  # inline code block
        else:
            description = re.sub(
                r'([*_]{2})(.+)\1', r'[b]\2[/b]', description
            )  # strong
            description = re.sub(r'([*_])(.+)\1', r'[i]\2[/i]', description)  # italic
            description = re.sub(
                r'(~{2})(.+)\1', r'[s]\2[/s]', description
            )  # strikethrough
            description = re.sub(
                r'`(.+)`', r'[code]\1[/code]', description
            )  # inline code block

        if uploading_to == 1:
            description = re.sub(
                r'\n-{5,}', r'\n[hr]', description
            )  # horizontal rule, FA style
        elif uploading_to == 5:
            description = re.sub(
                r'\n-{5,}', r'\n[rule]', description
            )  # horizontal rule, SF style
        else:
            description = re.sub(
                r'\n-{5,}', '', description
            )  # remove horizontal rule on other sites

    return description
