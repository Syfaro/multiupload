import os
import time

import requests
from flask import Flask
from flask import g
from flask import render_template
from flask import request
from influxdb import InfluxDBClient
from raven import fetch_git_sha
from flask_migrate import Migrate
from htmlmin.main import minify

from models import db
from routes.accounts import app as accounts_app
from routes.api import app as api_app
from routes.home import app as home_app
from routes.upload import app as upload_app
from routes.user import app as user_app
from routes.list import app as list_app
from sentry import sentry
from csrf import csrf
from utils import random_string

app = Flask(__name__)

app.config.from_object('config')
app.config['SENTRY_RELEASE'] = fetch_git_sha(os.path.join(os.path.dirname(__file__), '..'))

app.logger.propagate = True

app.register_blueprint(home_app)
app.register_blueprint(upload_app, url_prefix='/upload')
app.register_blueprint(user_app, url_prefix='/user')
app.register_blueprint(accounts_app, url_prefix='/account')
app.register_blueprint(list_app, url_prefix='/list')
app.register_blueprint(api_app, url_prefix='/api/v1')

app.jinja_env.globals['git_version'] = app.config['SENTRY_RELEASE']

migrate = Migrate(app, db, render_as_batch=True)


@app.before_request
def start_influx():
    influx = app.config.get('INFLUXDB', None)
    if not influx:
        return
    g.influx = InfluxDBClient(**influx)
    g.start = time.time()


@app.template_global('nonce')
def nonce() -> str:
    n = g.get('nonce')
    if n:
        return n
    g.nonce = random_string(24)
    return g.nonce


@app.after_request
def record_stats(resp):
    if not app.debug:
        if resp.content_type == 'text/html; charset=utf-8':
            resp.set_data(minify(resp.get_data(as_text=True)))

    if 'SENTRY_REPORT' in app.config:
        # sentry error reporter requires inline styles
        resp.headers['Content-Security-Policy'] = "default-src 'none';" \
                                                "script-src 'self' 'unsafe-inline' https: 'nonce-{1}' 'strict-dynamic';" \
                                                "object-src 'none';" \
                                                "style-src 'self' 'unsafe-inline' fonts.googleapis.com maxcdn.bootstrapcdn.com;" \
                                                "img-src 'self' blob: data:;" \
                                                "media-src 'none';" \
                                                "frame-src 'self';" \
                                                "font-src 'self' fonts.gstatic.com;" \
                                                "connect-src 'self' sentry.io;" \
                                                "base-uri 'none';" \
                                                "report-uri {0}".format(app.config['SENTRY_REPORT'], nonce())

    influx = g.get('influx', None)
    start_time = g.get('start', None)

    if not influx or not start_time:
        return resp

    if request.path.startswith('/static'):
        return resp

    try:
        influx.write_points([{
            'measurement': 'request',
            'tags': {
                'status_code': resp.status_code,
                'path': request.path,
            },
            'fields': {
                'duration': time.time() - start_time,
            },
        }])
    except requests.exceptions.ConnectionError:
        pass

    return resp


@app.errorhandler(500)
def internal_server_error(error):
    event, dsn = g.sentry_event_id, sentry.client.get_public_dsn('https')
    return render_template('500.html', event_id=event, public_dsn=dsn), 500


@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403


with app.app_context():
    sentry.init_app(app)
    csrf.init_app(app)

    db.init_app(app)
    db.create_all()

    from models import Site
    from sites.known import known_list
    for site in known_list():
        s = Site.query.get(site[0])
        if not s:
            s = Site(site[1])
            s.id = site[0]

            db.session.add(s)
    db.session.commit()

if __name__ == '__main__':
    app.run(threaded=True)
