import os
import time

import requests
from flask import Flask
from flask import g
from flask import render_template
from flask import request
from influxdb import InfluxDBClient
from raven import fetch_git_sha

from models import db
from routes.accounts import app as accounts_app
from routes.api import app as api_app
from routes.home import app as home_app
from routes.upload import app as upload_app
from routes.user import app as user_app
from sentry import sentry

app = Flask(__name__)

app.config.from_object('config')
app.config['SENTRY_RELEASE'] = fetch_git_sha(os.path.join(os.path.dirname(__file__), '..'))

app.logger.propagate = True

app.register_blueprint(home_app)
app.register_blueprint(upload_app)
app.register_blueprint(user_app, url_prefix='/user')
app.register_blueprint(accounts_app, url_prefix='/account')
app.register_blueprint(api_app, url_prefix='/api/v1')

app.jinja_env.globals['git_version'] = app.config['SENTRY_RELEASE'][:7]


@app.before_request
def start_influx():
    influx = app.config.get('INFLUXDB', None)
    if not influx:
        return
    g.influx = InfluxDBClient(**influx)
    g.start = time.time()


@app.after_request
def record_stats(resp):
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


if __name__ == '__main__':
    with app.app_context():
        sentry.init_app(app)

        db.init_app(app)
        db.create_all()

    app.run()
