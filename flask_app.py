
# A very simple Flask Hello World app for you to get started with...

from flask import Flask, render_template, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_user, LoginManager, UserMixin, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config["DEBUG"] = True

SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}".format(
    username="ishark",
    password="DXOLNJnc",
    hostname="ishark.mysql.pythonanywhere-services.com",
    databasename="ishark$comments",
)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# database creation:
# > ipython3.7
# > > from flask_app import db
# > > db.create_all()

app.secret_key = "tpCff4LR9ldTlZBUUmQO"
login_manager = LoginManager()
login_manager.init_app(app)

# to create a new user:
# > flask shell
# > from flask_app import db, User
# > from werkzeug.security import generate_password_hash
# newuser = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisOV=False, FAisADM=False, FAisAD=False)
# db.session.add(newuser)
# db.session.commit()

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    FAname = db.Column(db.String(128), nullable=False)
    FAid = db.Column(db.String(64))
    FAemail = db.Column(db.String(128))
    FAlastop = db.Column(db.DateTime)
    FAisFA = db.Column(db.Boolean, nullable=False)
    FAisOV = db.Column(db.Boolean, nullable=False)
    FAisADM = db.Column(db.Boolean, nullable=False)
    FAisAD = db.Column(db.Boolean, nullable=False)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return self.username

@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(username=user_id).first()

class Comment(db.Model):

    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(4096))
    posted = db.Column(db.DateTime, default=datetime.now)
    commenter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    commenter = db.relationship('User', foreign_keys=commenter_id)

@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("main_page.html", comments=Comment.query.all())

    if not current_user.is_authenticated:
        return redirect(url_for('index'))

    comment = Comment(content=request.form["contents"], commenter=current_user)
    db.session.add(comment)
    db.session.commit()

    return redirect(url_for('index'))

@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login_page.html", error=False)

    user = load_user(request.form["username"])
    if user is None:
        return render_template("login_page.html", error=True)

    if not user.check_password(request.form["password"]):
        return render_template("login_page.html", error=True)

    login_user(user)

    return redirect(url_for('index'))

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
