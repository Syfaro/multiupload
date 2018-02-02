from flask import Blueprint
from flask import jsonify
from flask import g
from flask import request

from utils import login_required

from models import Account

from constant import Sites

from description import parse_description

app = Blueprint('api', __name__)


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
