import requests
import simplecrypt
from flask import Blueprint
from flask import Response
from flask import g
from flask import jsonify
from flask import request
from flask import session
from simplecrypt import decrypt
from werkzeug.contrib.cache import SimpleCache

from constant import HEADERS
from constant import Sites
from description import parse_description
from models import Account
from models import db
from sites.deviantart import DeviantArt
from sites.known import known_list
from utils import login_required

app = Blueprint('api', __name__)

cache = SimpleCache()


@app.route('/sites')
def sites():
    s = []

    for site in known_list():
        s.append({
            'id': site[0],
            'name': site[1],
        })

    return jsonify({
        'sites': s,
    })


@app.route('/whoami')
@login_required
def whoami():
    return jsonify({
        'id': g.user.id,
        'username': g.user.username,
    })


@app.route('/accounts')
@login_required
def accounts():
    accts = []
    for account in Account.query.filter_by(user_id=g.user.id):
        accts.append({
            'id': account.id,
            'site_id': account.site_id,
            'site_name': account.site.name,
            'username': account.username,
        })

    return jsonify({
        'accounts': accts,
    })


@app.route('/description', methods=['POST'])
@login_required
def description():
    data = request.get_json()

    accts = data.get('accounts')
    desc = data.get('description')

    descriptions = []
    done = []

    for site in accts.split(','):
        s = Sites(int(site))

        if s.value in done or s == Sites.Twitter:
            continue

        descriptions.append({
            'site': s.name,
            'description': parse_description(desc, s.value),
        })

        done.append(s.value)

    return jsonify({
        'descriptions': descriptions,
    })


@app.route('/preview/description')
@login_required
def preview():
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


@app.route('/deviantart/category', methods=['GET'])
@login_required
def get_deviantart_category():
    path = request.args.get('path', '/')
    cached = cache.get('deviantart-' + path)
    if cached:
        return Response(cached, mimetype='application/json')

    account = request.args.get('account')

    a: Account = Account.query.get(account)

    da = DeviantArt.get_da()
    r = da.refresh_token(decrypt(session['password'], a.credentials))
    a.update_credentials(r['refresh_token'])
    db.session.commit()

    sub = requests.get('https://www.deviantart.com/api/v1/oauth2/stash/publish/categorytree', headers=HEADERS, params={
        'access_token': r['access_token'],
        'catpath': path,
    }).content

    cache.set('deviantart-' + path, sub, timeout=60*60*24)  # keep cached for 24 hours

    return Response(sub, mimetype='application/json')


@app.route('/deviantart/folders', methods=['GET'])
@login_required
def get_deviantart_folders():
    account = request.args.get('account')
    a: Account = Account.query.get(account)
    if a.user_id != g.user.id:
        return 'Bad.'

    decrypted = simplecrypt.decrypt(session['password'], a.credentials)
    da = DeviantArt(decrypted, a)

    return jsonify({
        'folders': da.get_folders(),
    })
