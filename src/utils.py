import re
import time
from functools import wraps
from random import SystemRandom
from string import ascii_lowercase
from subprocess import PIPE
from subprocess import Popen
from typing import List, Tuple
from typing import Union

import requests
from flask import current_app, flash
from flask import g
from flask import redirect
from flask import request
from flask import session
from flask import url_for
from werkzeug.datastructures import MultiDict

from models import Notice
from models import User
from sentry import sentry

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


def get_active_notices(user: Union[int, None] = None):
    notices: List[Notice] = Notice.find_active().all()

    if user:
        notices = filter(lambda notice: not notice.was_viewed_by(user), notices)

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
