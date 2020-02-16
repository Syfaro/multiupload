import time
from typing import Any, List

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
import simplecrypt

from multiupload.constant import Sites
from multiupload.models import Account, db
from multiupload.sentry import sentry
from multiupload.sites import AccountExists, BadCredentials, SiteError
from multiupload.sites.known import KNOWN_SITES, known_list
from multiupload.utils import login_required, send_to_influx

app = Blueprint('accounts', __name__)


@app.route('/manage')
@login_required
def manage() -> Any:
    return render_template('accounts/accounts.html', sites=known_list(), user=g.user)


@app.route('/add/<int:site_id>', methods=['GET'])
@login_required
def add(site_id: int) -> Any:
    try:
        site = Sites(site_id)
    except ValueError:
        return abort(404)

    extra_data = {}

    for known_site in KNOWN_SITES:
        if known_site.SITE == site:
            s = known_site()

            try:
                pre = s.pre_add_account()
            except SiteError as ex:
                sentry.captureException()
                flash('There was an error with the site: {msg}'.format(msg=ex.message))
                return redirect(url_for('accounts.manage'))

            if pre is not None:
                # Check if we got a dict, that's data we should add to our template
                if isinstance(pre, dict):
                    extra_data = pre
                # Not a dict, only other type is a Response we should return.
                # This is used for redirects for OAuth, etc.
                else:
                    return pre

    return render_template(
        'accounts/add_site/%d.html' % site_id,
        site=site,
        extra_data=extra_data,
        user=g.user,
    )


@app.route('/add/<int:site_id>/callback', methods=['GET'])
@login_required
def add_callback(site_id: int) -> Any:
    try:
        site = Sites(site_id)
    except:
        return abort(404)

    extra_data = {}

    for known_site in KNOWN_SITES:
        if known_site.SITE == site:
            s = known_site()

            try:
                callback = s.add_account_callback()
            except SiteError as ex:
                sentry.captureException()
                flash('There was an error with the site: {msg}'.format(msg=ex.message))
                return redirect(url_for('accounts.manage'))

            if callback is not None:
                if isinstance(callback, dict):
                    extra_data = callback
                else:
                    return callback

    return render_template(
        'accounts/add_site/%d.html' % site_id,
        site=site,
        extra_data=extra_data,
        user=g.user,
    )


@app.route('/add/<int:site_id>', methods=['POST'])
@login_required
def add_post(site_id: int) -> Any:
    try:
        site = Sites(site_id)
    except ValueError:
        return abort(404)

    start_time = time.time()

    try:
        for known_site in KNOWN_SITES:
            if known_site.SITE == site:
                s = known_site()
                data = s.parse_add_form(request.form)
                accounts = s.add_account(data)

                if s.supports_folder():
                    for account in accounts:
                        decrypted = simplecrypt.decrypt(
                            session['password'], account.credentials
                        )

                        s = known_site(decrypted, account)
                        s.get_folders()

    except BadCredentials:
        flash('Unable to authenticate.')
        return redirect(url_for('accounts.manage', site_id=site.value))

    except AccountExists:
        flash('Account already exists.')
        return redirect(url_for('accounts.manage'))

    send_to_influx(
        {
            'measurement': 'account_time_add',
            'fields': {'duration': time.time() - start_time},
            'tags': {'site': site.value},
        }
    )

    return redirect(url_for('accounts.manage'))


@app.route('/remove/<int:account_id>')
@login_required
def remove(account_id: int) -> Any:
    account = Account.find(account_id)

    if not account:
        return abort(404)

    return render_template('accounts/remove.html', account=account, user=g.user)


@app.route('/remove', methods=['POST'])
@login_required
def remove_post() -> Any:
    account_id = request.form['id']
    account = Account.find(account_id)

    if not account:
        return abort(404)

    db.session.delete(account)
    db.session.commit()

    flash('Account removed.')
    return redirect(url_for('accounts.manage'))


@app.route('/refresh/folders', methods=['GET'])
@login_required
def refresh_folders() -> Any:
    accounts: List[Account] = g.user.accounts

    for account in accounts:
        for known_site in KNOWN_SITES:
            if known_site.SITE == account.site:
                if not known_site.supports_folder():
                    continue

                decrypted = simplecrypt.decrypt(
                    session['password'], account.credentials
                )

                s = known_site(decrypted, account)
                s.get_folders(update=True)

    flash('Refreshed folders!')
    return redirect(url_for('accounts.manage'))
