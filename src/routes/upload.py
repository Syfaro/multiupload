from typing import List

import time
import simplecrypt

from flask import Blueprint
from flask import flash
from flask import g
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from requests import HTTPError

from constant import Sites

from description import parse_description

from models import Account
from models import Site
from models import db

from sentry import sentry

from sites import AccountExists
from sites import BadCredentials
from sites import SiteError

from sites.known import KNOWN_SITES
from sites.known import known_list

from submission import Submission

from utils import get_active_notices
from utils import login_required
from utils import send_to_influx

app = Blueprint('upload', __name__)


@app.route('/beta', methods=['GET'])
@app.route('/beta/<path:p>', methods=['GET'])
@login_required
def beta_upload(p=None):
    return render_template('app.html', user=g.user)


@app.route('/upload', methods=['GET'])
@login_required
def upload_form():
    return render_template('upload.html', user=g.user, sites=Site.query.all(),
                           notices=get_active_notices(for_user=g.user.id))


@app.route('/preview/description')
@login_required
def preview_description():
    accounts = request.args.getlist('account')
    description = request.args.get('description', '')

    descriptions = []
    sites_done = []

    for site in accounts:
        account = Account.query.filter_by(user_id=session['id']).filter_by(id=int(site)).first()

        if account.site.value in sites_done or account.site == Sites.Twitter:
            continue

        descriptions.append({
            'site': account.site.name,
            'description': parse_description(description, account.site.value),
        })

        sites_done.append(account.site.value)

    return jsonify({
        'descriptions': descriptions,
    })


def write_upload_time(start_time, site=None, measurement='upload_time'):
    duration = time.time() - start_time

    point = {
        'measurement': measurement,
        'fields': {
            'duration': duration,
        },
    }

    if site:
        point['tags'] = {'site': site}

    send_to_influx(point)


@app.route('/upload', methods=['POST'])
@login_required
def upload_post():
    total_time = time.time()

    title = request.form.get('title', None)
    description = request.form.get('description', None)
    keywords = request.form.get('keywords', None)
    rating = request.form.get('rating', None)

    upload = request.files.get('image', None)

    has_error = False

    if not title:
        flash('Missing title.')
        has_error = True

    if not description:
        flash('Missing description.')
        has_error = True

    if not keywords:
        flash('Missing keywords.')
        has_error = True

    if not upload:
        flash('Missing image.')
        has_error = True

    if not request.form.getlist('account'):
        flash('No site selected.')
        has_error = True

    if not rating:
        flash('No content rating selected.')
        has_error = True

    if has_error:
        return redirect(url_for('upload.upload_form'))

    submission = Submission(title, description, keywords, rating, upload)

    basic_error = False

    for account in Account.query.filter_by(user_id=g.user.id).all():
        account.used_last = 0

    accounts: List[Account] = []
    for acct in request.form.getlist('account'):
        account = Account.query.get(acct)

        if not account or account.user_id != g.user.id:
            flash('Account does not exist or does not belong to current user.')
            return redirect(url_for('upload.upload_form'))

        account.used_last = 1

        accounts.append(account)

    db.session.commit()

    if basic_error:
        return redirect(url_for('upload.upload_form'))

    accounts = sorted(accounts, key=lambda x: x.site_id)

    twitter_link_id = request.form.get('twitterlink', None)
    if twitter_link_id is not None:
        try:
            twitter_link_id = int(twitter_link_id)
        except ValueError:
            twitter_link_id = None
    twitter_link = None

    uploads: List[dict] = []
    for account in accounts:
        start_time = time.time()

        decrypted = simplecrypt.decrypt(session['password'], account.credentials)

        link = None

        for site in KNOWN_SITES:
            if site.SITE == account.site:
                s = site(decrypted, account)

                errors = s.validate_submission()
                if errors:
                    for error in errors:
                        flash(error)
                        continue

                try:
                    link = s.submit_artwork(submission, extra={
                        'twitter_link': twitter_link,
                    })

                except BadCredentials:
                    flash('Unable to upload on {site} to account {account}, you may need to log in again.'.format(
                        site=account.site.name, account=account.username))
                    continue

                except SiteError as ex:
                    flash('Unable to upload on {site} to account {account}: {msg}'.format(
                        site=account.site.name, account=account.username, msg=ex.message
                    ))
                    continue

                except HTTPError:
                    flash('Unable to upload on {site} to account {account} due to a site issue.'.format(
                        site=account.site.name, account=account.username
                    ))
                    continue

                uploads.append({
                    'link': link,
                    'name': '{site} - {account}'.format(site=site.SITE.name, account=account.username)
                })

        if account.id == twitter_link_id:
            twitter_link = link

        write_upload_time(start_time, account.site.value)

    write_upload_time(total_time, measurement='upload_time_total')

    return render_template('after_upload.html', uploads=uploads, user=g.user)


@app.route('/add')
@login_required
def add():
    return render_template('add_site.html', sites=known_list(), user=g.user)


@app.route('/add/<int:site_id>', methods=['GET'])
@login_required
def add_account_form(site_id):
    try:
        site = Sites(site_id)
    except ValueError:
        return 'Unknown site ID!'

    extra_data = {}

    for known_site in KNOWN_SITES:
        if known_site.SITE == site:
            s = known_site()

            try:
                pre = s.pre_add_account()
            except SiteError as ex:
                sentry.captureException()
                return 'There was an error with the site: {msg}'.format(msg=ex.message)

            if pre is not None:
                if isinstance(pre, dict):
                    extra_data = pre
                else:
                    return pre

    return render_template('add_site/%d.html' % site_id, site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>/callback', methods=['GET'])
@login_required
def add_account_callback(site_id):
    site = Sites(site_id)

    if not site:
        return 'Unknown site ID!'

    extra_data = {}

    for known_site in KNOWN_SITES:
        if known_site.SITE == site:
            s = known_site()

            try:
                callback = s.add_account_callback()
            except SiteError as ex:
                sentry.captureException()
                return 'There was an error with the site: {msg}'.format(msg=ex.message)

            if callback is not None:
                if isinstance(callback, dict):
                    extra_data = callback
                elif isinstance(callback, str):
                    return callback
                else:
                    return callback

    return render_template('add_site/%d.html' % site_id, site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>', methods=['POST'])
@login_required
def add_account_post(site_id):
    start_time = time.time()

    try:
        site = Sites(site_id)
    except ValueError:
        flash('Unknown site ID.')
        return redirect(url_for('upload.add_account_form'))

    try:
        for known_site in KNOWN_SITES:
            if known_site.SITE == site:
                s = known_site()
                data = s.parse_add_form(request.form)
                s.add_account(data)

    except BadCredentials:
        flash('Unable to authenticate')
        return redirect(url_for('upload.add_account_form', site_id=site.value))

    except AccountExists:
        flash('Account already exists.')
        return redirect(url_for('upload.upload_form'))

    send_to_influx({
        'measurement': 'account_time_add',
        'fields': {
            'duration': time.time() - start_time,
        },
        'tags': {
            'site': site.value,
        },
    })

    return redirect(url_for('upload.upload_form'))


@app.route('/remove/<int:account_id>')
@login_required
def remove_form(account_id):
    account = Account.query.get(account_id)

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('upload.upload_form'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('upload.upload_form'))

    return render_template('remove.html', account=account, user=g.user)


@app.route('/remove', methods=['POST'])
@login_required
def remove():
    account_id = request.form.get('id')
    if not account_id:
        flash('Missing account ID.')
        return redirect(url_for('upload.upload_form'))

    account = Account.query.get(account_id)

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('upload.upload_form'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('upload.upload_form'))

    db.session.delete(account)
    db.session.commit()

    flash('Account removed.')
    return redirect(url_for('upload.upload_form'))
