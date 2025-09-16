from app import db
from werkzeug.security import check_password_hash
from app.permissions import hasPrivilege, UT_MANAGER, UT_FA, UT_REFUGE, UT_ADOPTES, UT_DECEDES, UT_HIST, UT_FATEMP, UT_VETO, PRIV_ADMIN, PRIV_RFA, PRIV_REF, PRIV_ADDCD, PRIV_HIST, PRIV_SEARCH, PRIV_BSC, PRIV_RVETO, PRIV_RPLAN, PRIV_REGNUM, PRIV_APIR, PRIV_APIW, PRIV_ADDUNR
from flask_login import UserMixin
from datetime import datetime


class GlobalData(db.Model):

    __tablename__ = "globaldata"

    id = db.Column(db.Integer, primary_key=True)
    LastImportReg = db.Column(db.Integer)
    LastImportDate = db.Column(db.DateTime)
    LastSyncDate = db.Column(db.DateTime)


class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    usertype = db.Column(db.Integer)
    PrivStr = db.Column(db.String(64))
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
    PrivCOMPTA = db.Column(db.Boolean, default=False)
    PrivCOMPTAMOD = db.Column(db.Boolean, default=False)
    PrivCOMPTASELF = db.Column(db.Boolean, default=False)
#    cats = db.relationship('Cat', backref='owner_id', lazy='dynamic')
#    icats = db.relationship('Cat', backref='nextowner_id', lazy='dynamic')

    def __repr__(self):
        return "<User {}>".format(self.FAname)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return self.username

    # there does not seem to be an easy way to use constants in the templates without passing them
    # one by one as variables, so this utility functions "translate" the permissions into accessors
    def typeManager(self):
        return self.usertype == UT_MANAGER
    def typeFA(self):
        return self.usertype == UT_FA
    def typeRefuge(self):
        return self.usertype == UT_REFUGE
    def typeAdoptes(self):
        return self.usertype == UT_ADOPTES
    def typeDecedes(self):
        return self.usertype == UT_DECEDES
    def typeHistorique(self):
        return self.usertype == UT_HIST
    def typeFAtemp(self):
        return self.usertype == UT_FATEMP
    def typeVetoerinaire(self):
        return self.usertype == UT_VETO

    # same as above, but for permissions and menus
    def hasAdmin(self):
        return hasPrivilege(self, PRIV_ADMIN)
    def hasReferent(self):
        return hasPrivilege(self, PRIV_RFA)
    def hasRefuge(self):
        return hasPrivilege(self, PRIV_REF)
    def hasAdDcd(self):
        return hasPrivilege(self, PRIV_ADDCD)
    def hasHist(self):
        return hasPrivilege(self, PRIV_HIST)
    def hasSearch(self):
        return hasPrivilege(self, PRIV_SEARCH)
    def hasBonSteril(self):
        return hasPrivilege(self, PRIV_BSC)
    def hasRefugeVeto(self):
        return hasPrivilege(self, PRIV_RVETO)
    def hasRefugePlanVeto(self):
        return hasPrivilege(self, PRIV_RPLAN)
    def hasRegistre(self):
        return hasPrivilege(self, PRIV_REGNUM)
    def hasAPIread(self):
        return hasPrivilege(self, PRIV_APIR)
    def hasAPIwrite(self):
        return hasPrivilege(self, PRIV_APIW)
    def hasAddUnreg(self):
        return hasPrivilege(self, PRIV_ADDUNR)


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
        if self.regnum > 0:
            return "{}-{}".format(self.regnum%10000, int(self.regnum/10000))
        elif self.regnum == -1:
            return "N{}".format(self.id)
        else:
            return "P{}".format(self.id)

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
    transferred = db.Column(db.Boolean)
    validby_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    validby = db.relationship('User', foreign_keys=validby_id)
    validdate = db.Column(db.DateTime)
    comments = db.Column(db.String(1024))

    def __repr__(self):
        return "<VetInfo {}>".format(self.id)

class Facture(db.Model):

    __tablename__ = "factures"

    id = db.Column(db.Integer, primary_key=True)
    fdate = db.Column(db.DateTime)
    clinic = db.Column(db.String(32))
    clinic_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    facnumber = db.Column(db.String(64))
    duplicata = db.Column(db.Integer)
    total = db.Column(db.Numeric(6,2))
    paid = db.Column(db.Boolean)
    pdate = db.Column(db.DateTime)
    reconciled = db.Column(db.Boolean)
    rdate = db.Column(db.DateTime)
