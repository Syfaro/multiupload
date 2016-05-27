#!/usr/bin/env python
import base64, os, sys
sys.stdout.write("""
# A long and random string
SECRET_KEY = "{secret_key}"

# Enable debugging mode to help troubleshoot problems.
DEBUG = False

# Disable a feature in Flask-SQLAlchemy we don't use
SQLALCHEMY_TRACK_MODIFICATIONS = False
"""[1:].format(
    secret_key=base64.b64encode(os.urandom(48)).decode("ascii"),
))