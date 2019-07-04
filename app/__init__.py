from flask import Flask
from flask_qrcode import QRcode
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

app = Flask(__name__)

# determine if we are on the developement site
devel_site = '/ishark' in os.getcwd()

if devel_site:
    app.config.from_object('config-dev')
else:
    app.config.from_object('config')

db = SQLAlchemy(app)
qrcode = QRcode(app)

login_manager = LoginManager()
login_manager.init_app(app)

# kill caching
@app.after_request
def set_response_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

from app.web import *
