from typing import List
import json

import requests
from flask import Blueprint, Response, g, jsonify, request, session

import simplecrypt
from simplecrypt import decrypt
from multiupload.cache import cache
from multiupload.constant import HEADERS, Sites
from multiupload.description import parse_description
from multiupload.models import Account, SavedTemplate, SavedSubmission, User, db
from multiupload.sites.deviantart import DeviantArt
from multiupload.sites.known import known_list
from multiupload.utils import login_required

app = Blueprint('api', __name__)


@app.route('/sites')
def sites():
    s = []

    for site in known_list():
        s.append({'id': site[0], 'name': site[1]})

    return jsonify({'sites': s})


@app.route('/whoami')
def whoami():
    session_id = session.get('id')
    if session_id:
        user: User = User.query.get(session['id'])
        if user:
            return jsonify({'id': user.id, 'username': user.username})

    return jsonify({'id': None, 'username': None})


@app.route('/accounts')
@login_required
def accounts():
    accts: List[dict] = []
    for account in Account.all():
        accts.append(
            {
                'id': account.id,
                'site_id': account.site_id,
                'site_name': account.site.name,
                'username': account.username,
            }
        )

    return jsonify({'accounts': accts})


@app.route('/submissions')
@login_required
def submissions():
    subs = SavedSubmission.query.filter_by(user_id=g.user.id).all()

    subs = list(map(lambda sub: {
        'id': sub.id,
        'title': sub.title,
        'description': sub.description,
        'tags': sub.tags,
        'original_filename': sub.original_filename,
        'image_filename': sub.image_filename,
        'image_mimetype': sub.image_mimetype,
        'account_ids': sub.account_ids,
        'site_data': json.loads(sub.site_data),
        'group_id': sub.group_id,
        'master': sub.master,
    }, subs))

    return jsonify(subs)


@app.route('/description', methods=['POST'])
@login_required
def description():
    data = request.get_json()

    accts = data.get('accounts')
    desc = data.get('description')

    if not accts or not desc:
        return jsonify({'error': 'missing data'})

    descriptions = []
    done = []

    for site in accts.split(','):
        s = Sites(int(site))

        if (
            s.value in done or s == Sites.Twitter or s == Sites.Mastodon
        ):  # each site only needs to be done once, twitter doesn't get a preview
            continue

        descriptions.append(
            {'site': s.name, 'description': parse_description(desc, s.value)}
        )

        done.append(s.value)

    return jsonify({'descriptions': descriptions})


@app.route('/preview/description', methods=['POST'])
@login_required
def preview():
    accountlist: List[str] = request.form.getlist('account')
    orig_description: str = request.form.get('description', '')

    descriptions = []
    sites_done = []

    for site in accountlist:
        try:
            account = Account.find(int(site))
        except ValueError:
            continue

        if (
            not account
            or account.site.value in sites_done
            or account.site == Sites.Twitter
            or account.site == Sites.Mastodon
        ):
            continue

        descriptions.append(
            {
                'site': account.site.name,
                'description': parse_description(orig_description, account.site.value),
            }
        )

        sites_done.append(account.site.value)

    return jsonify({'descriptions': descriptions})


@app.route('/deviantart/category', methods=['GET'])
@login_required
def get_deviantart_category():
    path = request.args.get('path', '/')
    cached = cache.get('deviantart-' + path)
    if cached:
        return Response(cached, mimetype='application/json')

    account_id = request.args.get('account')
    try:
        account: Account = Account.find(int(account_id))
    except ValueError:
        return jsonify({'error': 'bad account'})

    da = DeviantArt.get_da()
    r = da.refresh_token(decrypt(session['password'], account.credentials))
    account.update_credentials(r['refresh_token'])
    db.session.commit()

    sub = requests.get(
        'https://www.deviantart.com/api/v1/oauth2/stash/publish/categorytree',
        headers=HEADERS,
        params={'access_token': r['access_token'], 'catpath': path},
    ).content

    cache.set(
        'deviantart-' + path, sub, timeout=60 * 60 * 24
    )  # keep cached for 24 hours

    return Response(sub, mimetype='application/json')


@app.route('/deviantart/folders', methods=['GET'])
@login_required
def get_deviantart_folders():
    account_id = request.args.get('account')

    try:
        account: Account = Account.find(int(account_id))
    except ValueError:
        return jsonify({'error': 'bad account'})

    decrypted = simplecrypt.decrypt(session['password'], account.credentials)
    da = DeviantArt(decrypted, account)

    return jsonify({'folders': da.get_folders()})


@app.route('/templates', methods=['GET'])
@login_required
def get_templates():
    templates = SavedTemplate.query.filter_by(user_id=g.user.id).all()

    return jsonify({'templates': list(map(lambda t: t.as_dict(), templates))})