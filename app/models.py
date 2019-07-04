from app import db
from werkzeug.security import check_password_hash
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    FAname = db.Column(db.String(128), nullable=False)
    FAid = db.Column(db.String(64))
    FAemail = db.Column(db.String(128))
    FAlastop = db.Column(db.DateTime)
    FAresp_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    numcats = db.Column(db.Integer)
    FAresp = db.relationship('User', foreign_keys=FAresp_id)
    FAisFA = db.Column(db.Boolean, default=False)
    FAisRF = db.Column(db.Boolean, default=False)
    FAisOV = db.Column(db.Boolean, default=False)
    FAisADM = db.Column(db.Boolean, default=False)
    FAisAD = db.Column(db.Boolean, default=False)
    FAisDCD = db.Column(db.Boolean, default=False)
    FAisVET = db.Column(db.Boolean, default=False)
    FAisHIST = db.Column(db.Boolean, default=False)
    FAisREF = db.Column(db.Boolean, default=False)
    FAisTEMP = db.Column(db.Boolean, default=False)
#    cats = db.relationship('Cat', backref='owner_id', lazy='dynamic')
#    icats = db.relationship('Cat', backref='nextowner_id', lazy='dynamic')

    def __repr__(self):
        return "<User {}>".format(self.FAname)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return self.username

# --------------- EVENT CLASS

class Event(db.Model):

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    cat_id = db.Column(db.Integer, db.ForeignKey('cats.id'), nullable=False)
    edate = db.Column(db.DateTime, default=datetime.now)
    etext = db.Column(db.String(1024))

# --------------- CAT CLASS

class Cat(db.Model):

    __tablename__ = "cats"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('User', foreign_keys=owner_id)
    temp_owner = db.Column(db.String(64))
    name = db.Column(db.String(32))
    sex = db.Column(db.Integer)
    color = db.Column(db.Integer)
    longhair = db.Column(db.Integer)
    birthdate = db.Column(db.DateTime)
    regnum = db.Column(db.Integer, unique=True, nullable=False)
    identif = db.Column(db.String(16))
    description = db.Column(db.String(2048))
    comments = db.Column(db.String(1024))
    vetshort = db.Column(db.String(16))
    adoptable = db.Column(db.Boolean)
    vetvisits = db.relationship('VetInfo', backref='cat', order_by='VetInfo.vdate', lazy=True)
    lastop = db.Column(db.DateTime)
    events = db.relationship('Event', backref='cat', order_by="Event.edate.desc()", lazy=True)

    def __repr__(self):
        return "<Cat {}>".format(self.regStr())

    def asText(self):
        str = ""
        if self.name:
            str += self.name
        else:
            str += "pas de nom"

        str += "(" + self.regStr()

        if self.identif:
            str += "/"+self.identif+")"
        else:
            str += ")"

        return str

    def regStr(self):
        return "{}-{}".format(self.regnum%10000, int(self.regnum/10000))

    def canAccess(self, fauser):
        return self.owner_id == fauser.id or fauser.FAisADM or (fauser.FAisRF and self.owner.FAresp_id == fauser.id)

# --------------- VETINFO CLASS

class VetInfo(db.Model):

    __tablename__ = "vetinfo"

    id = db.Column(db.Integer, primary_key=True)
    cat_id = db.Column(db.Integer, db.ForeignKey('cats.id'), nullable=False)
#    cat = db.relationship('Cat', foreign_keys=cat_id)
    doneby_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doneby = db.relationship('User', foreign_keys=doneby_id)
    vet_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vet = db.relationship('User', foreign_keys=vet_id)
    vtype = db.Column(db.String(16))
    vdate = db.Column(db.DateTime, default=datetime.now)
    planned = db.Column(db.Boolean)
    requested = db.Column(db.Boolean)
    validby_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    validby = db.relationship('User', foreign_keys=doneby_id)
    validdate = db.Column(db.DateTime)
    comments = db.Column(db.String(1024))

