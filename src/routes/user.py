import re
from random import SystemRandom
from string import ascii_letters
from typing import Union

import bcrypt
import passwordmeter
import requests
from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from jinja2 import Markup, escape, evalcontextfilter
from sqlalchemy import func

import simplecrypt
from cache import cache
from constant import Sites
from models import (
    Account,
    AccountConfig,
    NoticeViewed,
    SavedSubmission,
    SavedTemplate,
    User,
    db,
)
from utils import login_required

app = Blueprint('user', __name__)


_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')


@app.app_template_filter('nl2br')
@evalcontextfilter
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(
        u'<p>%s</p>' % p.replace('\n', Markup('<br>\n'))
        for p in _paragraph_re.split(escape(value))
    )
    if eval_ctx.autoescape:
        result = Markup(result)
    return result


@app.route('/dismiss', methods=['POST'])
@login_required
def dismiss_notice():
    alert = request.form.get('id')

    viewed = NoticeViewed(alert, g.user.id)

    db.session.add(viewed)
    db.session.commit()

    return 'Saved'


@app.route('/email/verify', methods=['GET'])
def email_verify():
    verifier = request.args.get('verifier')

    if not verifier:
        flash('Missing verifier.')
        return redirect(url_for('home.home'))

    user: User = User.query.filter_by(email_verifier=verifier).first()

    if user.email_verified:
        flash('Email was already verified!')
        return redirect(url_for('home.home'))

    user.email_verified = True
    db.session.commit()

    session['username'] = user.username

    flash('Email verified!')
    return redirect(url_for('home.home'))


@app.route('/email/subscribe')
@login_required
def email_subscribe():
    requests.post(
        current_app.config['MAILGUN_LIST_ENDPOINT'],
        auth=('api', current_app.config['MAILGUN_KEY']),
        data={'subscribed': True, 'address': g.user.email, 'name': g.user.username},
    )

    g.user.email_subscribed = True
    db.session.commit()

    flash('Subscribed to mailing list!')
    return redirect(url_for('user.settings'))


@app.route('/email/unsubscribe')
@login_required
def email_unsubscribe():
    requests.delete(
        current_app.config['MAILGUN_LIST_ENDPOINT'] + '/' + g.user.email,
        auth=('api', current_app.config['MAILGUN_KEY']),
    )

    g.user.email_subscribed = False
    db.session.commit()

    flash('Removed from mailing list.')
    return redirect(url_for('user.settings'))


@app.route('/email', methods=['GET'])
@login_required
def change_email():
    return render_template('user/change_email.html')


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
    g.user.email_verifier = ''.join(
        SystemRandom().choice(ascii_letters) for _ in range(16)
    )

    with open('templates/email.txt') as f:
        email_body = f.read()

    requests.post(
        current_app.config['MAILGUN_ENDPOINT'],
        auth=('api', current_app.config['MAILGUN_KEY']),
        data={
            'from': current_app.config['MAILGUN_ADDRESS'],
            'to': email,
            'subject': 'Verify your Furry Art Multiuploader email address',
            'h:Reply-To': 'syfaro@huefox.com',
            'text': email_body.format(
                username=g.user.username,
                link=current_app.config['MAILGUN_VERIFY'].format(g.user.email_verifier),
            ),
        },
    )

    flash('A link was sent to you to verify your email address.')

    db.session.commit()

    return redirect(url_for('user.settings'))


@app.route('/username', methods=['GET'])
@login_required
def change_username():
    return render_template('user/change_username.html')


@app.route('/username', methods=['POST'])
@login_required
def change_username_post():
    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        flash('Missing new username or password.')
        return redirect(url_for('user.change_username'))

    if not g.user.verify(password):
        flash('Incorrect password.')
        return redirect(url_for('user.change_username'))

    if (
        User.by_name_or_email(username)
        and username.casefold() != g.user.username.casefold()
    ):
        flash('Username is already in use.')
        return redirect(url_for('user.change_username'))

    g.user.username = username
    db.session.commit()

    flash('Username changed!')
    return redirect(url_for('user.settings'))


@app.route('/password', methods=['GET'])
@login_required
def change_password():
    return render_template('user/change_password.html')


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
        flash(
            'Weak password. You may wish to try the following suggestions.<br><ul><li>%s</ul></ul>'
            % ('</li><li>'.join(improvements.values()))
        )
        return redirect(url_for('user.change_password_form'))

    if not g.user.verify(current_password):
        flash('Current password is incorrect.')
        return redirect(url_for('user.change_password_form'))

    g.user.password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

    for account in Account.query.filter_by(user_id=g.user.id).all():
        decrypted = simplecrypt.decrypt(current_password, account.credentials)
        encrypted = simplecrypt.encrypt(new_password, decrypted)
        account.credentials = encrypted

    db.session.commit()

    flash('Password changed.')
    return redirect(url_for('user.settings'))


@app.route('/reset', methods=['GET'])
def password_reset():
    return render_template('user/reset.html')


@app.route('/reset', methods=['POST'])
def password_reset_post():
    email = request.form.get('email')
    if not email:
        flash('Missing email address')
        return redirect(url_for('user.password_reset'))

    user: User = User.query.filter(func.lower(User.email) == func.lower(email)).first()

    if not user:
        flash('Unknown email address')
        return redirect(url_for('user.password_reset'))

    if not user.email_verified:
        flash('Email was not verified')
        return redirect(url_for('user.password_reset'))

    user.email_reset_verifier = ''.join(
        SystemRandom().choice(ascii_letters) for _ in range(16)
    )
    db.session.commit()

    with open('templates/user/reset.txt') as f:
        email_body = f.read()

    requests.post(
        current_app.config['MAILGUN_ENDPOINT'],
        auth=('api', current_app.config['MAILGUN_KEY']),
        data={
            'from': current_app.config['MAILGUN_ADDRESS'],
            'to': user.email,
            'subject': 'Reset your Furry Art Multiuploader password',
            'h:Reply-To': 'syfaro@huefox.com',
            'text': email_body.format(
                username=user.username,
                link=current_app.config['MAILGUN_RESET'].format(
                    user.email_reset_verifier
                ),
            ),
        },
    )

    flash('An email was sent to reset your password!')
    return redirect(url_for('user.password_reset'))


@app.route('/reset/verify', methods=['GET'])
def password_reset_verify():
    if session.get('verifier'):
        verifier = session.pop('verifier')
    else:
        verifier = request.args.get('verifier')

    if not verifier:
        return 'Missing verifier'

    user: User = User.query.filter_by(email_reset_verifier=verifier).first()

    if not user:
        return 'Unknown verifier'

    return render_template('user/reset_password.html')


@app.route('/reset/verify', methods=['POST'])
def password_reset_verify_post():
    verifier = request.form.get('verifier')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm-password')

    if not verifier or not password or not confirm_password:
        flash('Missing data')
        session['verifier'] = verifier
        return redirect(url_for('user.password_reset_verify'))

    if password != confirm_password:
        flash('Passwords do not match')
        session['verifier'] = verifier
        return redirect(url_for('user.password_reset_verify'))

    user: User = User.query.filter_by(email_reset_verifier=verifier).first()

    if not user:
        return 'Unknown verifier'

    for submission in SavedSubmission.query.filter_by(user_id=user.id).all():
        db.session.delete(submission)
    db.session.commit()

    for account in user.accounts:
        for config in AccountConfig.query.filter_by(account_id=account.id).all():
            db.session.delete(config)
        db.session.commit()

        db.session.delete(account)
    db.session.commit()

    user.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user.email_reset_verifier = ''

    db.session.commit()

    flash('Password was reset, welcome back {0}!'.format(user.username))

    session['id'] = user.id
    session['password'] = password

    return redirect(url_for('upload.create_art'))


@app.route('/settings')
@login_required
def settings():
    sofurry = []
    furaffinity = []
    tumblr = []
    twitter_hashtag = []
    twitter_noimg = []

    for account in g.user.accounts:
        site = Sites(account.site_id)

        if site == Sites.SoFurry:
            remap = account['remap_sofurry']

            sofurry.append(
                {
                    'id': account.id,
                    'username': account.username,
                    'enabled': remap and remap.val == 'yes',
                }
            )
        elif site == Sites.FurAffinity:
            resolution = account['resolution_furaffinity']

            furaffinity.append(
                {
                    'id': account.id,
                    'username': account.username,
                    'enabled': not resolution or resolution.val == 'yes',
                }
            )
        elif site == Sites.Tumblr:
            header = account['tumblr_title']

            tumblr.append(
                {
                    'id': account.id,
                    'username': account.username,
                    'enabled': header and header.val == 'yes',
                }
            )
        elif site == Sites.Twitter:
            hashtag = account['nsfw_hashtag']

            twitter_hashtag.append(
                {
                    'id': account.id,
                    'username': account.username,
                    'enabled': hashtag and hashtag.val == 'yes',
                }
            )

            noimage = account['twitter_noimage']

            twitter_noimg.append(
                {
                    'id': account.id,
                    'username': account.username,
                    'enabled': noimage and noimage.val == 'yes',
                }
            )

    return render_template(
        'user/settings.html',
        sites={
            'sofurry': sofurry,
            'furaffinity': furaffinity,
            'tumblr': tumblr,
            'twitter_hashtag': twitter_hashtag,
            'twitter_noimage': twitter_noimg,
        },
        themes=get_themes(),
    )


@app.route('/sofurry/remap', methods=['POST'])
@login_required
def settings_sofurry_remap_post():
    sofurry_accounts = [
        account for account in g.user.accounts if account.site == Sites.SoFurry
    ]

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
    furaffinity_accounts = [
        account for account in g.user.accounts if account.site == Sites.FurAffinity
    ]

    for account in furaffinity_accounts:
        resolution = account['resolution_furaffinity']

        if not resolution:
            resolution = AccountConfig(account.id, 'resolution_furaffinity', 'yes')
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
    tumblr_accounts = [
        account for account in g.user.accounts if account.site == Sites.Tumblr
    ]

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


@app.route('/twitter/nsfw', methods=['POST'])
@login_required
def settings_twitter_nsfw():
    twitter_accounts = [
        account for account in g.user.accounts if account.site == Sites.Twitter
    ]

    for account in twitter_accounts:
        hashtag = account['nsfw_hashtag']

        if not hashtag:
            hashtag = AccountConfig(account.id, 'nsfw_hashtag', 'no')
            db.session.add(hashtag)

        if request.form.get('account[{id}]'.format(id=account.id)) == 'on':
            hashtag.val = 'yes'
        else:
            hashtag.val = 'no'

    db.session.commit()

    return redirect(url_for('user.settings'))


@app.route('/twitter/noimage', methods=['POST'])
@login_required
def settings_twitter_noimage():
    twitter_accounts = [
        account for account in g.user.accounts if account.site == Sites.Twitter
    ]

    for account in twitter_accounts:
        hashtag = account['twitter_noimage']

        if not hashtag:
            hashtag = AccountConfig(account.id, 'twitter_noimage', 'no')
            db.session.add(hashtag)

        if request.form.get('account[{id}]'.format(id=account.id)) == 'on':
            hashtag.val = 'yes'
        else:
            hashtag.val = 'no'

    db.session.commit()

    return redirect(url_for('user.settings'))


@app.route('/theme', methods=['POST'])
@login_required
def update_theme():
    theme_name = request.form.get('theme')

    if theme_name == 'Default':
        g.user.theme = None
        g.user.theme_url = None
    else:
        theme = get_theme_by_name(theme_name)

        g.user.theme = theme['name']
        g.user.theme_url = theme['cssCdn']

    db.session.commit()

    flash('Theme updated!')
    return redirect(url_for('user.settings'))


def get_theme_by_name(name: str) -> Union[None, dict]:
    themes = get_themes()

    for theme in themes.get('themes'):
        if theme.get('name') == name:
            return theme

    return None


def get_themes() -> dict:
    cached = cache.get('theme')
    if cached:
        return cached

    r = requests.get('https://bootswatch.com/api/4.json').json()

    cache.set('theme', r)

    return r


@app.route('/template', methods=['GET'])
@login_required
def get_template():
    templates = SavedTemplate.query.filter_by(user_id=g.user.id).all()

    return render_template('user/template.html', templates=templates)


@app.route('/template', methods=['POST'])
@login_required
def post_template():
    name = request.form.get('name')
    content = request.form.get('content')

    if not name or not content:
        flash('Missing name or content.')
        return redirect(url_for('user.get_template'))

    template = SavedTemplate(g.user, name, content)

    db.session.add(template)
    db.session.commit()

    flash('Added template!')

    return redirect(url_for('user.get_template'))


@app.route('/template/remove', methods=['POST'])
@login_required
def post_template_remove():
    template_id = request.form.get('id')

    template = (
        SavedTemplate.query.filter_by(user_id=g.user.id)
        .filter_by(id=template_id)
        .first()
    )

    if not template:
        flash('Unknown template.')
        return redirect(url_for('user.get_template'))

    db.session.delete(template)
    db.session.commit()

    flash('Removed template!')
    return redirect(url_for('user.get_template'))
