from random import SystemRandom
from string import ascii_letters

import bcrypt
import passwordmeter
import requests
import simplecrypt
from flask import Blueprint, session, current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from constant import Sites
from models import Account, User
from models import AccountConfig
from models import NoticeViewed
from models import db
from utils import login_required

app = Blueprint('user', __name__)


@app.route('/dismiss/<int:alert>', methods=['POST'])
@login_required
def dismiss_notice(alert):
    viewed = NoticeViewed(alert, g.user.id)

    db.session.add(viewed)
    db.session.commit()

    return 'Saved'


@app.route('/email/verify', methods=['GET'])
def email_verify():
    verifier = request.args.get('verifier')

    if not verifier:
        return 'Missing verifier.'

    user: User = User.query.filter_by(email_verifier=verifier).first()

    if user.email_verified:
        return 'Already verified.'

    user.email_verified = True

    db.session.commit()

    flash('Email verified!')

    session['username'] = user.username

    return redirect(url_for('home.home'))


@app.route('/email/subscribe')
@login_required
def email_subscribe():
    requests.post(current_app.config['MAILGUN_LIST_ENDPOINT'], auth=('api', current_app.config['MAILGUN_KEY']), data={
        'subscribed': True,
        'address': g.user.email,
        'name': g.user.username,
    })

    g.user.email_subscribed = True
    db.session.commit()

    flash('Subscribed to mailing list!')
    return redirect(url_for('user.settings'))


@app.route('/email/unsubscribe')
@login_required
def email_unsubscribe():
    requests.delete(current_app.config['MAILGUN_LIST_ENDPOINT'] + '/' + g.user.email,
                    auth=('api', current_app.config['MAILGUN_KEY']))

    g.user.email_subscribed = False
    db.session.commit()

    flash('Removed from mailing list.')
    return redirect(url_for('user.settings'))


@app.route('/email', methods=['GET'])
@login_required
def change_email():
    return render_template('change_email.html', user=g.user)


@app.route('/email', methods=['POST'])
@login_required
def change_email_post():
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash('Missing data')
        return redirect(url_for('user.change_email'))

    if not g.user.verify(password):
        flash('Incorrect password')
        return redirect(url_for('user.change_email'))

    g.user.email = email
    g.user.email_verified = 0
    g.user.email_verifier = ''.join(SystemRandom().choice(ascii_letters) for _ in range(16))

    with open('templates/email.txt') as f:
        email_body = f.read()

    requests.post(current_app.config['MAILGUN_ENDPOINT'], auth=('api', current_app.config['MAILGUN_KEY']), data={
        'from': current_app.config['MAILGUN_ADDRESS'],
        'to': email,
        'subject': 'Verify your Furry Art Multiuploader email address',
        'h:Reply-To': 'syfaro@huefox.com',
        'text': email_body.format(username=g.user.username,
                                  link=current_app.config['MAILGUN_VERIFY'].format(g.user.email_verifier))
    })

    flash('A link was sent to you to verify your email address.')

    db.session.commit()

    return redirect(url_for('user.settings'))


@app.route('/password', methods=['GET'])
@login_required
def change_password():
    return render_template('change_password.html', user=g.user)


@app.route('/password', methods=['POST'])
@login_required
def change_password_post():
    current_password = request.form.get('current_password', None)
    new_password = request.form.get('new_password', None)
    new_password_confirm = request.form.get('new_password_confirm', None)

    if not current_password:
        flash('Missing current password.')
        return redirect(url_for('user.change_password_form'))

    if not new_password:
        flash('Missing new password.')
        return redirect(url_for('user.change_password_form'))

    if not new_password_confirm or new_password != new_password_confirm:
        flash('Password confirmation does not match.')
        return redirect(url_for('user.change_password_form'))

    strength, improvements = passwordmeter.test(new_password)
    if strength < 0.3:
        flash('Weak password. You may wish to try the following suggestions.<br><ul><li>%s</ul></ul>' %
              ('</li><li>'.join(improvements.values())))
        return redirect(url_for('user.change_password_form'))

    if not g.user.verify(current_password):
        flash('Current password is incorrect.')
        return redirect(url_for('user.change_password_form'))

    g.user.password = bcrypt.hashpw(
        new_password.encode('utf-8'), bcrypt.gensalt())

    for account in Account.query.filter_by(user_id=g.user.id).all():
        decrypted = simplecrypt.decrypt(current_password, account.credentials)
        encrypted = simplecrypt.encrypt(new_password, decrypted)
        account.credentials = encrypted

    db.session.commit()

    flash('Password changed.')
    return redirect(url_for('user.settings'))


@app.route('/settings')
@login_required
def settings():
    sofurry = []
    furaffinity = []
    tumblr = []

    for account in g.user.accounts:
        site = Sites(account.site_id)

        if site == Sites.SoFurry:
            remap = account['remap_sofurry']

            sofurry.append({
                'id': account.id,
                'username': account.username,
                'enabled': remap and remap.val == 'yes'
            })
        elif site == Sites.FurAffinity:
            resolution = account['resolution_furaffinity']

            furaffinity.append({
                'id': account.id,
                'username': account.username,
                'enabled': not resolution or resolution.val == 'yes'
            })
        elif site == Sites.Tumblr:
            header = account['tumblr_title']

            tumblr.append({
                'id': account.id,
                'username': account.username,
                'enabled': header and header.val == 'yes'
            })

    return render_template('settings.html', user=g.user, sofurry=sofurry, furaffinity=furaffinity, tumblr=tumblr)


@app.route('/sofurry/remap', methods=['POST'])
@login_required
def settings_sofurry_remap_post():
    sofurry_accounts = [account for account in g.user.accounts if account.site == Sites.SoFurry]

    for account in sofurry_accounts:
        remap = account['remap_sofurry']

        if not remap:
            remap = AccountConfig(account.id, 'remap_sofurry', 'no')
            db.session.add(remap)

        if request.form.get('account[{id}]'.format(id=account.id)) == 'on':
            remap.val = 'yes'
        else:
            remap.val = 'no'

    db.session.commit()

    return redirect(url_for('user.settings'))


@app.route('/furaffinity/resolution', methods=['POST'])
@login_required
def settings_furaffinity_resolution_post():
    furaffinity_accounts = [account for account in g.user.accounts if account.site == Sites.FurAffinity]

    for account in furaffinity_accounts:
        resolution = account['resolution_furaffinity']

        if not resolution:
            resolution = AccountConfig(
                account.id, 'resolution_furaffinity', 'yes')
            db.session.add(resolution)

        if request.form.get('account[{id}]'.format(id=account.id)) == 'on':
            resolution.val = 'yes'
        else:
            resolution.val = 'no'

    db.session.commit()

    return redirect(url_for('user.settings'))


@app.route('/tumblr/title', methods=['POST'])
@login_required
def settings_tumblr_title_post():
    tumblr_accounts = [account for account in g.user.accounts if account.site == Sites.Tumblr]

    for account in tumblr_accounts:
        header = account['tumblr_title']

        if not header:
            header = AccountConfig(account.id, 'tumblr_title', 'no')
            db.session.add(header)

        if request.form.get('account[{id}]'.format(id=account.id)) == 'on':
            header.val = 'yes'
        else:
            header.val = 'no'

    db.session.commit()

    return redirect(url_for('user.settings'))
