import os
import re
import time
import uuid
from functools import wraps
from random import SystemRandom
from string import ascii_lowercase
from subprocess import PIPE, Popen
from typing import List, Tuple, Union, Optional

import requests
from flask import current_app, flash, g, redirect, request, session, url_for
from werkzeug.datastructures import MultiDict

from multiupload.models import Notice, User
from multiupload.sentry import sentry

rng = SystemRandom()

RESIZE_EXP = re.compile(r'(?P<height>\d+)\D{1,}(?P<width>\d+)')


def random_string(length) -> str:
    return ''.join(rng.choice(ascii_lowercase) for _ in range(length))


def git_version() -> str:
    gitproc = Popen(['git', 'rev-parse', 'HEAD'], stdout=PIPE)
    (stdout, _) = gitproc.communicate()
    return stdout.strip().decode('utf-8')


def english_series(items) -> str:
    items = tuple(items)
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(x for x in items[:-1]) + ', and ' + items[-1]


def tumblr_blog_name(url):
    return url.split('//')[-1].split('/')[0]


def get_active_notices(user: Optional[int] = None):
    notices: List[Notice] = Notice.find_active().all()

    if user:
        notices = list(filter(lambda notice: not notice.was_viewed_by(user), notices))

    return notices


def send_to_influx(point: dict) -> None:
    influx = g.get('influx', None)

    if not influx:
        return

    try:
        influx.write_points([point])
    except requests.exceptions.ConnectionError:
        sentry.captureException()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id' not in session:
            flash('You must log in before you can view this page.')

            session['redir'] = request.path

            # See if we have a query string and can decode it
            # Query string is needed for OAuth redirect
            try:
                query = request.query_string.decode('utf-8')
            except:
                query = None

            if query:
                session['redir'] += '?' + query

            return redirect(url_for('home.home'))

        user: User = User.query.get(session['id'])

        if not user:
            session.pop('id')
            session['redir'] = request.path
            return redirect(url_for('home.home'))

        sentry.client.user_context(
            {'id': user.id, 'username': user.username, 'email': user.email}
        )

        g.user = user

        return f(*args, **kwargs)

    return decorated_function


def save_multi_dict(d: MultiDict) -> dict:
    n = {}

    for k, v in d.items():
        i = d.getlist(k)
        if len(i) > 1:
            n[k] = i
        else:
            n[k] = i[0]

    return n


def safe_ext(name: str) -> Union[bool, str]:
    if '.' not in name:
        return False

    split = name.rsplit('.', 1)[1].lower()
    if split not in current_app.config['ALLOWED_EXTENSIONS']:
        return False

    return split


def write_upload_time(
    start_time, site: int = None, measurement: str = 'upload_time'
) -> None:
    duration = time.time() - start_time

    point = {'measurement': measurement, 'fields': {'duration': duration}}

    if site:
        point['tags'] = {'site': site}

    send_to_influx(point)


def write_site_response(site: int, req: requests.Response) -> None:
    point = {
        'measurement': 'site_response',
        'fields': {'duration': req.elapsed.total_seconds()},
        'tags': {
            'site': site,
            'method': req.request.method,
            'status_code': req.status_code,
        },
    }

    send_to_influx(point)


def parse_resize(s: str) -> Union[None, Tuple[int, int]]:
    match = RESIZE_EXP.match(s.strip())
    if not match:
        return None

    try:
        height = int(match.group('height'))
        width = int(match.group('width'))
    except ValueError:
        return None

    return height, width


def clear_recorded_pages() -> None:
    """
    clear recorded pages, if there are any.
    """
    if hasattr(g, 'debug_pages'):
        g.debug_pages = []


def record_page(page: requests.Response) -> None:
    """
    record a page for debugging later.
    :param page: the page to record
    """
    if not hasattr(g, 'debug_pages'):
        g.debug_pages = []

    g.debug_pages.append(page)


def save_debug_pages() -> None:
    """
    if the user has saving page responses enabled, save them to the debug folder.
    record the page url, status code, and content.

    if there is history, also record the same data for all pages in history.
    :param pages: the pages to save data for
    """
    if not g.user.save_errors:
        return

    request_uuid = str(uuid.uuid4())
    folder = os.path.join(current_app.config['DEBUG_FOLDER'], request_uuid)

    os.mkdir(folder)

    pages = g.debug_pages

    with open(os.path.join(folder, 'info.txt'), 'w') as f:
        f.write('Recorded At: %d\n\n' % time.time())

        f.write('User ID: %d\n' % g.user.id)
        f.write('User Name: %s\n' % g.user.username)
        if g.user.email:
            f.write('User Email: %s\n' % g.user.email)

    idx = 1
    for page in pages:
        with open(os.path.join(folder, '%02d.txt' % idx), 'w') as f:
            f.write('URL: %s\n' % page.url)
            f.write('Status Code: %d\n' % page.status_code)

        with open(os.path.join(folder, '%02d.html' % idx), 'wb') as f:
            f.write(page.content)

        if page.history:
            h_idx = 1
            for history in page.history:
                with open(
                    os.path.join(folder, '%02d-%02d.txt' % (idx, h_idx)), 'w'
                ) as h:
                    h.write('URL: %s\n' % history.url)
                    h.write('Status Code: %d\n' % history.status_code)

                with open(
                    os.path.join(folder, '%02d-%02d.html' % (idx, h_idx)), 'wb'
                ) as h:
                    h.write(history.content)

                h_idx += 1

        idx += 1

    g.debug_pages = []
