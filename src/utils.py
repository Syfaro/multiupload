from functools import wraps
from random import SystemRandom
from string import ascii_lowercase
from subprocess import PIPE
from subprocess import Popen

import requests

from flask import g
from flask import redirect
from flask import session
from flask import url_for

from models import Notice
from models import User

from sentry import sentry

rng = SystemRandom()


def random_string(length):
    return ''.join(rng.choice(ascii_lowercase) for _ in range(length))


def git_version():
    gitproc = Popen(['git', 'rev-parse', 'HEAD'], stdout=PIPE)
    (stdout, _) = gitproc.communicate()
    return stdout.strip().decode('utf-8')


def english_series(items):
    items = tuple(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(x for x in items[:-1]) + ', and ' + items[-1]


def tumblr_blog_name(url):
    return url.split("//")[-1].split("/")[0]


def get_active_notices(for_user=None):
    notices = Notice.find_active().all()

    if for_user:
        notices = filter(lambda notice: not notice.was_viewed_by(for_user), notices)

    return notices


def send_to_influx(point):
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
            return redirect(url_for('home.home'))

        user = User.query.get(session['id'])

        if not user:
            session.pop('id')
            return redirect(url_for('home.home'))

        g.user = user

        return f(*args, **kwargs)

    return decorated_function
