import time

from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from constant import Sites
from models import Account
from models import db
from sentry import sentry
from sites import AccountExists
from sites import BadCredentials
from sites import SiteError
from sites.known import KNOWN_SITES
from sites.known import known_list
from utils import login_required
from utils import send_to_influx

app = Blueprint('accounts', __name__)


@app.route('/manage')
@login_required
def manage():
    return render_template('accounts/accounts.html', sites=known_list(), user=g.user)


@app.route('/add/<int:site_id>', methods=['GET'])
@login_required
def add(site_id):
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

    return render_template('accounts/add_site/%d.html' % site_id, site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>/callback', methods=['GET'])
@login_required
def add_callback(site_id):
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

    return render_template('accounts/add_site/%d.html' % site_id, site=site, extra_data=extra_data, user=g.user)


@app.route('/add/<int:site_id>', methods=['POST'])
@login_required
def add_post(site_id):
    start_time = time.time()

    try:
        site = Sites(site_id)
    except ValueError:
        flash('Unknown site ID.')
        return redirect(url_for('accounts.manage'))

    try:
        for known_site in KNOWN_SITES:
            if known_site.SITE == site:
                s = known_site()
                data = s.parse_add_form(request.form)
                s.add_account(data)

    except BadCredentials:
        flash('Unable to authenticate')
        return redirect(url_for('accounts.manage', site_id=site.value))

    except AccountExists:
        flash('Account already exists.')
        return redirect(url_for('accounts.manage'))

    send_to_influx({
        'measurement': 'account_time_add',
        'fields': {
            'duration': time.time() - start_time,
        },
        'tags': {
            'site': site.value,
        },
    })

    return redirect(url_for('accounts.manage'))


@app.route('/remove/<int:account_id>')
@login_required
def remove(account_id):
    account = Account.query.get(account_id)

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('accounts.manage'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('accounts.manage'))

    return render_template('accounts/remove.html', account=account, user=g.user)


@app.route('/remove', methods=['POST'])
@login_required
def remove_post():
    account_id = request.form.get('id')
    if not account_id:
        flash('Missing account ID.')
        return redirect(url_for('accounts.manage'))

    account = Account.query.get(account_id)

    if not account:
        flash('Account does not exist.')
        return redirect(url_for('accounts.manage'))

    if account.user_id != g.user.id:
        flash('Account does not belong to you.')
        return redirect(url_for('accounts.manage'))

    db.session.delete(account)
    db.session.commit()

    flash('Account removed.')
    return redirect(url_for('accounts.manage'))
