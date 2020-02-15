from flask import Blueprint, g, jsonify
from authlib.integrations.flask_oauth2 import current_token

from multiupload.oauth import authorization, require_oauth
from multiupload.utils import login_required
from multiupload.csrf import csrf


app = Blueprint('oauth', __name__)


@app.route('/authorize', methods=['GET', 'POST'])
@login_required
def authorize():
    return authorization.create_authorization_response(grant_user=g.user)


@app.route('/token', methods=['POST'])
@csrf.exempt
def issue_token():
    return authorization.create_token_response()


@app.route('/userinfo')
@require_oauth('profile')
def userinfo():
    user = current_token.user

    return jsonify({'id': user.id, 'name': user.username, 'email': user.email})
