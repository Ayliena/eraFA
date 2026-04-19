from app import db
from werkzeug.security import check_password_hash
from app.permissions import NUM_MENUS, NUM_PRIVS, UT_FA, UT_MANAGER, UT_REFUGE, UT_AD, UT_DCD, UT_RS, UT_HIST, UT_FATEMP, UT_VETO, MENU_FA, MENU_VET, MENU_RFA, MENU_PROC, MENU_COMPTA, MENU_ADMIN, PRIV_RFA, PRIV_RFATEMP, PRIV_SUPER, PRIV_REF, PRIV_ADR, PRIV_HIST, PRIV_SEARCH, PRIV_PEC, PRIV_BSC, PRIV_ADDCAT, PRIV_COMPTA, PRIV_CMMOD, PRIV_CMSELF, PRIV_USERS, PRIV_ADMIN, PRIV_REGNUM, PRIV_MOVE, PRIV_BVETO, PRIV_RVETO, PRIV_APIR, PRIV_APIW, TabUserTypes, TabPrivs, PRIV_CFA, PRIV_CAD, PRIV_EVENTS
from app.staticdata import FAC_FROZEN, FAC_UNPAID, FAC_PAID, FAC_RECONC, FAC_BEINGPAID
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
    FAresp = db.relationship('User', foreign_keys=FAresp_id, remote_side=[id], backref='managedFAs')
    numcats = db.Column(db.Integer)
    APIkey = db.Column(db.String(64))
    APIkey_exp = db.Column(db.DateTime)
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
    def typeFA(self):
        return self.usertype == UT_FA
    def typeManager(self):
        return self.usertype == UT_MANAGER
    def typeRefuge(self):
        return self.usertype == UT_REFUGE
    def typeAdoptes(self):
        return self.usertype == UT_AD
    def typeDecedes(self):
        return self.usertype == UT_DCD
    def typeRelaches(self):
        return self.usertype == UT_RS
    def typeHistorique(self):
        return self.usertype == UT_HIST
    def typeFAtemp(self):
        return self.usertype == UT_FATEMP
    def typeVeterinaire(self):
        return self.usertype == UT_VETO

    # same as above, but for permissions and menus
    def menuFA(self):
        return self.hasMenu(MENU_FA)
    def menuVET(self):
        return self.hasMenu(MENU_VET)
    def menuRFA(self):
        return self.hasMenu(MENU_RFA)
    def menuPROC(self):
        return self.hasMenu(MENU_PROC)
    def menuCOMPTA(self):
        return self.hasMenu(MENU_COMPTA)
    def menuADMIN(self):
        return self.hasMenu(MENU_ADMIN)

    def hasReferent(self):
        return self.hasPrivilege(PRIV_RFA)
    def hasReferentFAtemp(self):
        return self.hasPrivilege(PRIV_RFATEMP)
    def hasSuperviseur(self):
        return self.hasPrivilege(PRIV_SUPER)
    def hasRefuge(self):
        return self.hasPrivilege(PRIV_REF)
    def hasAdDcdRs(self):
        return self.hasPrivilege(PRIV_ADR)
    def hasHist(self):
        return self.hasPrivilege(PRIV_HIST)
    def hasSearch(self):
        return self.hasPrivilege(PRIV_SEARCH)
    def hasPriseEnCharge(self):
        return self.hasPrivilege(PRIV_PEC)
    def hasBonSteril(self):
        return self.hasPrivilege(PRIV_BSC)
    def hasContratFA(self):
        return self.hasPrivilege(PRIV_CFA)
    def hasContratAD(self):
        return self.hasPrivilege(PRIV_CAD)
    def hasAddUnreg(self):
        return self.hasPrivilege(PRIV_ADDCAT)
    def hasCompta(self):
        return self.hasPrivilege(PRIV_COMPTA)
    def hasComptaMod(self):
        return self.hasPrivilege(PRIV_CMMOD)
    def hasComptaSelf(self):
        return self.hasPrivilege(PRIV_CMSELF)
    def hasUsers(self):
        return self.hasPrivilege(PRIV_USERS)
    def hasAdmin(self):
        return self.hasPrivilege(PRIV_ADMIN)
    def hasRegNum(self):
        return self.hasPrivilege(PRIV_REGNUM)
    def hasMove(self):
        return self.hasPrivilege(PRIV_MOVE)
    def hasBonVeto(self):
        return self.hasPrivilege(PRIV_BVETO)
    def hasRefugeVeto(self):
        return self.hasPrivilege(PRIV_RVETO)
    def hasAPIread(self):
        return self.hasPrivilege(PRIV_APIR)
    def hasAPIwrite(self):
        return self.hasPrivilege(PRIV_APIW)
    def hasEvents(self):
        return self.hasPrivilege(PRIV_EVENTS)


    # check that the privilieges definition for this user is correct
    def checkPrivileges(self):
        # if length of string is less than PRIV_NUMBER, expend and pad with zeroes
        if not self.PrivStr or len(self.PrivStr) < NUM_PRIVS:
            self.PrivStr = self.PrivStr.rjust(NUM_PRIVS, '0')
        return True

    # set/unset a privilege (note: also works on menus)
    def setPrivilege(self, pn, val):
        self.checkPrivileges()
        # validate
        if pn >= len(self.PrivStr):
            return False

        # note: we don't check if it was already set/unset
        nps = self.PrivStr[:pn] + ("1" if val else "0") + self.PrivStr[pn+1:]
        self.PrivStr = nps
        return True

    def hasPrivilege(self, pn):
        if not self.PrivStr or pn >= len(self.PrivStr):
            return False

        if self.PrivStr[pn] == '1':
            return True

        return False

    def hasPrivilegeAny(self, pna):
        for pn in pna:
            if self.hasPrivilege(pn):
                return True

        return False

    def hasMenu(self, mn):
        if mn > NUM_MENUS or mn >= len(self.PrivStr):
            return False

        if self.PrivStr[mn] == '1':
            return True

        return False

    def defineMenus(self):
        if self.usertype == UT_VETO:
            self.setPrivilege(MENU_FA, 0)
            self.setPrivilege(MENU_VET, 1)
        elif self.usertype == UT_MANAGER:
            self.setPrivilege(MENU_FA, 0)
            self.setPrivilege(MENU_VET, 0)
        else:
            self.setPrivilege(MENU_FA, 1)
            self.setPrivilege(MENU_VET, 0)

        if self.hasPrivilegeAny([PRIV_RFA, PRIV_SUPER, PRIV_REF, PRIV_ADR, PRIV_HIST, PRIV_SEARCH, PRIV_ADDCAT]):
            self.setPrivilege(MENU_RFA, 1)
        else:
            self.setPrivilege(MENU_RFA, 0)

        if self.hasPrivilegeAny([PRIV_PEC, PRIV_BSC, PRIV_CFA, PRIV_CAD]):
            self.setPrivilege(MENU_PROC, 1)
        else:
            self.setPrivilege(MENU_PROC, 0)

        if self.hasPrivilegeAny([PRIV_COMPTA, PRIV_CMSELF, PRIV_CMMOD]):
            self.setPrivilege(MENU_COMPTA, 1)
        else:
            self.setPrivilege(MENU_COMPTA, 0)

        if self.hasUsers() or self.hasAdmin():
            self.setPrivilege(MENU_ADMIN, 1)
        else:
            self.setPrivilege(MENU_ADMIN, 0)

    def usertypeStr(self):
        if self.usertype < 0 or self.usertype > UT_VETO:
            return "invalid"

        return TabUserTypes[self.usertype]

    def privilegesStr(self):
        self.checkPrivileges()
        rv = ""
        sep = ""

        for i in range(len(self.PrivStr)):
            if self.PrivStr[i] == '1':
                rv += sep+TabPrivs[i]
                sep = " "

        return rv



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

    def isPrivate(self):
        if self.regnum < -1:
            return True
        else:
            return False

    def isUnreg(self):
        if self.regnum == -1:
            return True
        else:
            return False

    def nameFA(self):
        if self.owner.typeFAtemp():
            return "[{}]".format(self.temp_owner)
        if self.owner.typeRefuge():
            return "Refuge/{}".format(self.temp_owner)
        return self.owner.FAname

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
    validby_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
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
    total = db.Column(db.Numeric(8,2))
    state = db.Column(db.Integer)
    beingpaidby_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    beingpaidby = db.relationship('User', foreign_keys=beingpaidby_id)
    pdate = db.Column(db.DateTime)
    rdate = db.Column(db.DateTime)

    def isFrozen(self):
        return self.state == FAC_FROZEN

    def isUnpaid(self):
        return self.state == FAC_UNPAID

    def isPaid(self):
        return self.state == FAC_PAID

    def isBeingPaid(self):
        return self.state == FAC_BEINGPAID

    def isReconciled(self):
        return self.state == FAC_RECONC

    def statusText(self):
        if self.isUnpaid():
            return "A payer"
        elif self.isFrozen():
            return '<span class="bg-warning-subtle">En attente</span>'
        elif self.isBeingPaid():
            return '<span class="bg-warning">En réglement ({})</span>'.format(self.beingpaidby.FAname)
        elif self.isPaid():
            return '<span class="bg-success-subtle">Réglée le {}</span>'.format(self.pdate.strftime("%Y-%m-%d %H:%M"))
        elif self.isReconciled():
            return '<span class="bg-success-subtle">Réglée le {}</span> <span class="text-success">OK BANQUE le {}</span>'.format(self.pdate.strftime("%Y-%m-%d %H:%M"), self.rdate.strftime("%Y-%m-%d"))

