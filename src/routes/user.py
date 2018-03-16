import bcrypt
import passwordmeter
import simplecrypt
from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from constant import Sites
from models import Account
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
    return redirect(url_for('upload.upload_form'))


@app.route('/')
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
