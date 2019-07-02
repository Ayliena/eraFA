
# ERA FA management flask app

# jsonify is for debugging
import string
from flask import Flask, render_template, redirect, request, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, or_
from flask_login import login_user, LoginManager, UserMixin, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import secrets
from datetime import datetime, timedelta
import os
import hashlib
import base64
from PIL import Image
from flask_qrcode import QRcode

UPLOAD_FOLDER = '/home/ishark/eraFA/static'
ALLOWED_EXTENSIONS = set(['jpg'])

app = Flask(__name__)
app.config["DEBUG"] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

qrcode = QRcode(app)

# database creation:
# > ipython3.7
# > > from flask_app import db
# > > db.create_all()

# database backup/restore
# > mysqldump -u ishark -h ishark.mysql.pythonanywhere-services.com 'ishark$comments'  > db-backup.sql
# RESTORE: DANGEROUS! > mysql -u ishark -h ishark.mysql.pythonanywhere-services.com 'ishark$comments'  < db-backup.sql

app.secret_key = "tpCff4LR9ldTlZBUUmQO"
login_manager = LoginManager()
login_manager.init_app(app)


# --------------- STATIC DATA

# this maps DB field number to the string
# NOTE they must match the ones used in cat_page.html
DBTabColor = ["INCONNU", "BEIGE", "BEIGE ET BLANC", "BLANC", "BLUE POINT", "CREME", "ECAILLE DE TORTUE", "GRIS", "GRIS CHARTREUX", "GRIS ET BLANC",
             "NOIR", "NOIR ET BLANC", "NOIR ET SMOKE", "NOIR PLASTRON BLANC", "ROUX", "ROUX ET BLANC", "SEAL POINT", "TABBY BLANC", "TABBY BRUN", "TABBY GRIS",
             "TIGRE", "TIGRE BEIGE", "TIGRE BRUN", "TIGRE CREME", "TIGRE GRIS", "TRICOLORE"]
DBTabSex = ["INCONNU", "FEMELLE", "MALE"]
DBTabHair = ["COURT", "MI-LONG", "LONG"]

# these are the readable (html page) versions
TabColor = ["??couleur??", "Beige", "Beige et blanc", "Blanc", "Blue point", "Crème", "Ecaille de tortue", "Gris", "Gris chartreux", "Gris et blanc",
             "Noir", "Noir et blanc", "Noir et smoke", "Noir plastron blanc", "Roux", "Roux et blanc", "Seal point", "Tabby blanc", "Tabby brun", "Tabby gris",
             "Tigré", "Tigré beige", "Tigré brun", "Tigré crème", "Tigré gris", "Tricolore"]
TabSex = ["??sexe??", "Femelle", "Mâle"]
TabHair = ["", ", poil mi-long", ", poil long"]


#TabHair = ["COURT", "MI-LONG", "LONG"]


# constants
ACC_NONE = 0   # no access to data
ACC_RO = 1     # read-only (view) access
ACC_FULL = 2   # full access and edit, but not transfer
ACC_TOTAL = 3  # full access and transfer

# --------------- HELPER FUNCTIONS

def vetMapToString(vetmap, prefix):
    str =["-", "-", "-", "-", "-", "-", "-", "-"]
    if prefix+"_pv" in vetmap:
        str[0] = 'V'
    if prefix+"_r1" in vetmap:
        str[1] = '1'
    if prefix+"_r2" in vetmap:
        str[2] = '2'
    if prefix+"_sc" in vetmap:
        str[3] = 'S'
    if prefix+"_id" in vetmap:
        str[4] = 'P'
    if prefix+"_tf" in vetmap:
        str[5] = 'T'
    if prefix+"_gen" in vetmap:
        str[6] = 'X'
    if prefix+"_rr" in vetmap:
        str[7] = 'R'
    return "".join(str)

def vetStringToMap(vetstr, prefix):
    vmap = {}
    vmap[prefix+"_pv"] = (str[0] == 'V')
    vmap[prefix+"_r1"] = (str[1] == '1')
    vmap[prefix+"_r2"] = (str[2] == '2')
    vmap[prefix+"_sc"] = (str[3] == 'S')
    vmap[prefix+"_id"] = (str[4] == 'P')
    vmap[prefix+"_tf"] = (str[5] == 'T')
    vmap[prefix+"_gen"] = (str[6] == 'X')
    vmap[prefix+"_rr"] = (str[7] == 'R')
    return vmap

def vetAddStrings(vetstr1, vetstr2):
    str = list(vetstr1)
    for i in range(0,8):
        if str[i] == '-':
            str[i] = vetstr2[i]

    return "".join(str)

def ERAsum(str1):
    m = hashlib.md5()
    m.update((str1 + '0C1s5qzQo5').encode('utf-8'))
    str2 = base64.b64encode(m.digest()).decode('utf-8')

    return str2[0:12]

#
# --------------- DATABASE INITIALIZATION (required special FAs)
#
# > export FLASK_APP=flask_app.py
# > flask shell
# > from flask_app import db, User
# > newuserAD = User(username="--adopted--", password_hash="nologinAD", FAname="Chats adoptes", FAid="ADOPTIONS", FAemail="invalid@invalid", FAisAD=True)
# > newuserDCD = User(username="--decedes--", password_hash="nologinDCD", FAname="Chats decedes", FAid="DECES", FAemail="invalid@invalid", FAisDCD=True)
# > newuserHIST = User(username="--historique--", password_hash="nologinHIST", FAname="Chats: historique", FAid="HISTORIQUE", FAemail="invalid@invalid", FAisHIST=True)
# > newuserREF = User(username="--refuge--", password_hash="nologinREF", FAname="Refuge ERA", FAid="REFUGE", FAemail="invalid@invalid", FAisREF=True)
# > newuserTEMP = User(username="--fatemp--", password_hash="nologinTEMP", FAname="FA temporaires", FAid="FA_TEMP", FAemail="invalid@invalid", FAisTEMP=True)
# > db.session.add(newuserAD)
# > db.session.add(newuserDCD)
# > db.session.add(newuserHIST)
# > db.session.add(newuserREF)
# > db.session.add(newuserTEMP)
# > db.session.commit()
#
# IMPORTANT: the special FAs are stored statically here, so this must be set with the correct IDs
# special FA ids (static): AD DCD HIST REF TEMP
FAidSpecial = [2, 5, 10, 18, 90]


# --------------- USER CLASS

# to create a new user:
# > export FLASK_APP=flask_app.py
# > flask shell
# > from flask_app import db, User
# > from werkzeug.security import generate_password_hash
# > newuser = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=False)
# > newuserFA = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True)
# > newuserVET = User(username="login", password_hash=generate_password_hash("password"), FAname="VET name(long)", FAid="name(short)", FAemail="invalid@invalid", FAisVET=True)
# > db.session.add(newuser)
# > db.session.commit()
#

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(username=user_id).first()

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
    validated = db.Column(db.Boolean)
    comments = db.Column(db.String(1024))



#class Comment(db.Model):
#
#    __tablename__ = "comments"
#
#    id = db.Column(db.Integer, primary_key=True)
#    content = db.Column(db.String(4096))
#    posted = db.Column(db.DateTime, default=datetime.now)
#    commenter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
#    commenter = db.relationship('User', foreign_keys=commenter_id)

# kill caching
@app.after_request
def set_response_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# test page

@app.route('/misc', methods=["GET", "POST"])
@app.route('/misc/<int:cat_id>', methods=["GET"])
@login_required
def miscpage(cat_id=-1):
    if request.method == "POST":
        return render_template("misc_page.html", user=current_user, FAids=FAidSpecial, msg="POST REQUEST, id={} cmd={}".format(request.form["id"], request.form["action"]))

#    return render_template("misc_page.html", user=current_user, FAids=FAidSpecial, msg="GET REQUEST: id={}".format(cat_id))
    catlist = Cat.query.filter_by(name='FILOU').all()
    return render_template("bonveto_page.html", user=current_user, FAids=FAidSpecial, cats=catlist, fa=current_user, bdate=datetime.now(), vtype=(1,2,3,4,5,6), comments=["1 echographie", "1 autre echographie"])

# --------------- WEB PAGES

@app.route('/', methods=["GET", "POST"])
@app.route('/index', methods=["GET", "POST"])
def index():
    cats = Cat.query.filter_by(adoptable=True).all();

    # TODO split in pages of 10 or something....
    return render_template("adopt_page.html", tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, catlist=cats)


@app.route('/fa', methods=["GET", "POST"])
def fapage():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    # generate the page
    if request.method == "GET":
        # handle any message
        if "pendingmessage" in session:
            message = session["pendingmessage"]
            session.pop("pendingmessage")
        else:
            message = []

        # decide which type of page to display
        mode = None
        if "otherMode" in session:
            mode = session["otherMode"]

            # these are only allowed for SV/ADM
            if (mode == "special-all" or mode == "special-adopt" or mode == "special-search") and not (current_user.FAisOV or current_user.FAisADM):
                mode = None

        # display current user pages or alternate user's?
        # we can see pages of other FAs if we are OV/ADM or we are the FA's resp
        FAid = current_user.id
        if "otherFA" in session:
            FAid = session["otherFA"]
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if not faexists:
                return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

            # permissions: ADM and OV see all
            # RF can see the ones they manage + adopt/dead/refuge
            if not (current_user.FAisRF and theFA.FAresp_id != current_user.id) and not (current_user.FAisRF and (FAid == FAidSpecial[0] or
                        FAid == FAidSpecial[1] or FAid == FAidSpecial[3])) and not (current_user.FAisOV or current_user.FAisADM):
                FAid = current_user.id

        # handle special cases
        if mode == "special-vetplan":
            # query all vetinfo which are planned and associated with cats owned by the FA
            theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==True)).order_by(VetInfo.vdate).all()

            if FAid != current_user.id:
                return render_template("vet_page.html", user=current_user, otheruser=theFA, visits=theVisits, FAids=FAidSpecial, msg=message)

            return render_template("vet_page.html", user=current_user, visits=theVisits, FAids=FAidSpecial, msg=message)

        elif mode == "special-all":
            return render_template("list_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                listtitle="Tableau global des chats", catlist=Cat.query.order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message)

        elif mode == "special-adopt":
            return render_template("list_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                listtitle="Chats disponibles à l'adoption", catlist=Cat.query.filter_by(adoptable=True).order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message, adoptonly=True)

        elif mode == "special-search":
            searchfilter = session["searchFilter"]

            (src_name, src_regnum, src_id) = searchfilter.split(';')

            # rules for search: OR mode always
            # name and id: substring searches
            # regnum: if nnn-yy then exact match, if nnn then startswith match
            cats = []

            if src_name:
                cats = cats + Cat.query.filter(Cat.name.contains(src_name)).all()

            if src_regnum:
                if src_regnum.find('-') != -1:
                    # exact match
                    rr = src_regnum.split('-')
                    rn = int(rr[0]) + 10000*int(rr[1])

                    cats = cats + Cat.query.filter_by(regnum=rn).all()

                elif src_regnum.isdigit():
                    # fix number, all years
                    clause = "NOT MOD (regnum-"+src_regnum+",10000)"
                    cats = cats + Cat.query.filter(clause).all()

            if src_id:
                cats = cats + Cat.query.filter(Cat.identif.contains(src_id)).all()

            # we then use the /list page to display the cat list
            return render_template("list_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                listtitle="Résultat de la recherche", catlist=cats, FAids=FAidSpecial, msg=message)

        if FAid != current_user.id:
            return render_template("main_page.html", user=current_user, otheruser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                cats=Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message)

        return render_template("main_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
            cats=Cat.query.filter_by(owner_id=current_user.id).order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message)

    # handle POST commands
    cmd = request.form["action"]

    # alternate GET command for another FA
    if cmd == "sv_fastate":
        FAid = int(request.form["FAid"]);
        # note: we do not perform any check on the validity of FAid or on the access privileges,
        # since they will be performed by the GET method

        session["otherMode"] = None
        session["otherFA"] = FAid
        return redirect(url_for('fapage'))

    # get the cat
    theCat = Cat.query.filter_by(id=request.form["catid"]).first()
    if theCat == None:
        return render_template("error_page.html", user=current_user, errormessage="invalid cat id", FAids=FAidSpecial)
        return redirect(url_for('fapage'))

    # check if you can access this
    if theCat.owner_id != current_user.id and not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data", FAids=FAidSpecial)
#        return redirect(url_for('fapage'))

    if cmd == "adm_histcat" and current_user.FAisADM:
        # move the cat to the historical list of cats
        newFA = User.query.filter_by(id=FAidSpecial[2]).first()
        theCat.owner.numcats -= 1
        newFA.numcats += 1
        theCat.owner_id = newFA.id
        theCat.adoptable = False
        theCat.lastop = datetime.now()
        session["pendingmessage"] = [ [0, "Chat {} déplacé dans l'historique".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré dans l'historique".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()

    if cmd == "adm_deletecat" and current_user.FAisADM:
        # erase the cat and all the associated information from the database
        # NOTE THAT THIS IS IRREVERSIBLE AND LEAVES NO TRACE
        session["pendingmessage"] = [ [0, "Chat {} effacé du systeme".format(theCat.asText())] ]

        # start by erasing the image (if any)
        if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum))):
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))

        theCat.owner.numcats -= 1
        Event.query.filter_by(cat_id=theCat.id).delete()
        VetInfo.query.filter_by(cat_id=theCat.id).delete()
        db.session.delete(theCat)
        current_user.FAlastop = datetime.now()
        db.session.commit()

    return redirect(url_for('fapage'))


@app.route("/self")
@login_required
def selfpage():
    # a version of the main page which brings you back to your list
    session.pop("otherFA", None)
    session.pop("otherMode", None)
    session.pop("searchFilter", None)
    return redirect(url_for('fapage'))


@app.route("/cat", methods=["POST"])
@app.route('/cat/<int:catid>', methods=["GET"])
@login_required
def catpage(catid=-1):
    if request.method == "GET":
        if catid == -1:
            return redirect(url_for('fapage'))

        # we simulate a post request with action = fa_viewcat
        cmd = 'fa_viewcat'

    elif request.method == "POST":
        cmd = request.form["action"]

        if "catid" in request.form and request.form["catid"] != 'None':
            catid = int(request.form["catid"])

    if cmd == "fa_return":
        return redirect(url_for('fapage'))

    # generate an empty page for the addition of a Refu dossier
    if cmd == "adm_refucat" and current_user.FAisADM:
        return redirect(url_for('refupage'))

    # generate an empty page to add a new cat
    if cmd == "adm_newcat" and current_user.FAisADM:
        theCat = Cat(regnum=0)
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).all(), FAids=FAidSpecial)

    if (cmd == "adm_addcathere" or cmd == "adm_addcatputFA") and current_user.FAisADM:
        # generate the new cat using the form information
        vetstr = vetMapToString(request.form, "visit")

        try:
            bdate = datetime.strptime(request.form["c_birthdate"], "%d/%m/%y")
        except ValueError:
            bdate = None

        # convert registre
        rr = request.form["c_registre"].split('-')
        rn = int(rr[0]) + 10000*int(rr[1])

        theCat = Cat(regnum=rn, temp_owner=request.form["c_fatemp"], name=request.form["c_name"], sex=request.form["c_sex"], birthdate=bdate,
                    color=request.form["c_color"], longhair=request.form["c_hlen"], identif=request.form["c_identif"],
                    description=request.form["c_description"], comments=request.form["c_comments"], vetshort=vetstr,
                    adoptable=(request.form["c_adoptable"]=="1"))

        # ensure that registre is unique
        checkCat = Cat.query.filter_by(regnum=rn).first()

        if checkCat:
            # this is bad, we regenerate the page wit the current data
            message = [ [3, "Le numéro de registre existe déjà!"] ]
            theCat.regnum = 0
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).all(), msg=message, FAids=FAidSpecial)

        # if for any reason the FA is invalid, then put it here
        if cmd != "adm_addcathere":
            FAid = int(request.form["FAid"]);
            # validate the id
            newFA = User.query.filter_by(id=FAid).first()
            faexists = newFA is not None;

            if cmd == "adm_addcatputFA" and faexists:
                newFA.numcats += 1
                theCat.owner_id = FAid
            else:
                current_user.numcats += 1
                theCat.owner_id = current_user.id

        else: # cmd == "addcathere"
            current_user.numcats += 1
            theCat.owner_id = current_user.id

        db.session.add(theCat)
        # make sure we have an id
        db.session.commit()

        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} rajouté dans le système".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: rajoute dans le systeme".format(current_user.FAname))
        db.session.add(theEvent)

        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('fapage'))

    # existing cat, populate the page with the available data
    theCat = Cat.query.filter_by(id=catid).first();
    if theCat == None:
        return render_template("error_page.html", user=current_user, errormessage="invalid cat id", FAids=FAidSpecial)
#        return redirect(url_for('fapage'))

    # if we're working on another user's cats, show the information on top of the page
    FAid = current_user.id
    access = ACC_NONE

    if "otherFA" in session:
        FAid = session["otherFA"]
        theFA = User.query.filter_by(id=FAid).first()
        faexists = theFA is not None;

        if not faexists:
            return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

    # upgrade access depending on our status
    # OV can see anything in RO mode
    if current_user.FAisOV:
        access = ACC_RO

    # we can always see our cats, and ADM can always see all
    if current_user.FAisFA and theCat.owner_id == current_user.id:
        access = ACC_FULL

    # we also have full access to any cat a FA we resp
    if theCat.owner.FAresp_id == current_user.id:
        access = ACC_FULL

    if current_user.FAisADM:
        access = ACC_TOTAL

    # if no access, no access....
    if access == ACC_NONE:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data", FAids=FAidSpecial)

    # vet list will be needed
    VETlist = User.query.filter_by(FAisVET=True).all()

    if access == ACC_RO:
        # FAid != current_user.id is implied
        return render_template("cat_page.html", user=current_user, otheruser=theFA, cat=theCat, readonly=True, VETids=VETlist, FAids=FAidSpecial)

    # if we reach here, we have at least ACC_FULL
    # some operations may still be unavailable!

    FAlist = []
    if access == ACC_TOTAL:
        FAlist = User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).order_by(User.FAid).all()

    # handle generation of the page
    if cmd == "fa_viewcat":
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, VETids=VETlist, FAids=FAidSpecial)

    # cat commands
    if cmd == "fa_modcat" or cmd == "fa_modcatr":
        # return jsonify(request.form.to_dict())

        # update cat information and indicate what was changed
        # info is Adoppt Name Ident Sex Birthdate L(hairlen) Color (c)omments Description Picture
        updated = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        if theCat.name != request.form["c_name"]:
            theCat.name = request.form["c_name"]
            updated[1] = 'N'

        # only deal with this for FATEMP cats
        if theCat.owner_id == FAidSpecial[4]:
            if theCat.temp_owner != request.form["c_fatemp"]:
                # we indicate this as a transfer
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré de [{}] a [{}]".format(current_user.FAname, theCat.temp_owner, request.form["c_fatemp"]))
                db.session.add(theEvent)
                theCat.temp_owner = request.form["c_fatemp"]

        if theCat.sex != int(request.form["c_sex"]):
            theCat.sex=request.form["c_sex"]
            updated[3] = 'S'

        try:
            bd = datetime.strptime(request.form["c_birthdate"], "%d/%m/%y")
        except ValueError:
            bd = None

        if theCat.birthdate != bd:
            theCat.birthdate = bd
            updated[4] = "B"

        if theCat.color != int(request.form["c_color"]):
            theCat.color=request.form["c_color"]
            updated[6] = 'C'

        if theCat.longhair != int(request.form["c_hlen"]):
            theCat.longhair=request.form["c_hlen"]
            updated[5] = 'L'

        if theCat.identif != request.form["c_identif"]:
            theCat.identif=request.form["c_identif"]
            updated[2] = 'I'

        if theCat.comments != request.form["c_comments"]:
            theCat.comments=request.form["c_comments"]
            updated[7] = 'c'

        if theCat.description != request.form["c_description"]:
            theCat.description=request.form["c_description"]
            updated[8] = 'D'

        if theCat.adoptable != (request.form["c_adoptable"] == "1"):
            theCat.adoptable=(request.form["c_adoptable"] == "1")
            updated[0] = 'A'

        if 'img_erase' in request.form:
            # delete the file (existing or not....)
            if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum))):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))
                updated[9] = 'P'
        else:
           if 'img_file' in request.files:
                img_file = request.files['img_file']

                if img_file:
                    filename = secure_filename(img_file.filename)
                    img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    # now rename the file and strip metadata (resize also???)
                    theImage = Image.open(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    theImage.save(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    updated[9] = 'P'

        # indicate moodification of the data
        updated = "".join(updated)

        if updated != "----------":
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: mise à jour des informations {}".format(current_user.FAname, updated))
            db.session.add(theEvent)
            cat_updated = True
        else:
            cat_updated = False

        # generate the vetinfo record, if any, and the associated event
        VisitType = vetMapToString(request.form, "visit")

        if VisitType != "--------":
            # validate the vet
            vet = next((x for x in VETlist if x.id==int(request.form["visit_vet"])), None)

            if not vet:
                return render_template("error_page.html", user=current_user, errormessage="vet id is invalid", FAids=FAidSpecial)
            else:
                vetId = vet.id

            try:
                VisitDate = datetime.strptime(request.form["visit_date"], "%d/%m/%y")
            except ValueError:
                VisitDate = datetime.now()

            VisitPlanned = (int(request.form["visit_state"]) == 1)

            # if executed, then cumulate with the global
            if not VisitPlanned:
                theCat.vetshort = vetAddStrings(theCat.vetshort, VisitType)
                et = "effectuee le"
                cat_updated = True
            else:
                et = "planifiee pour le"

            theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vetId, vtype=VisitType, vdate=VisitDate,
                planned=VisitPlanned, comments=request.form["visit_comments"])
            db.session.add(theVisit)
            db.session.commit()  # needed for vet.FAname

            # add it as event (planned or not)
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, VisitType, et, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
            db.session.add(theEvent)

        # iterate through all the planned visits and see if they have been updated....
        # extract all planned visits which are now executed
        modvisits = []
        for k in request.form.keys():
            if k.startswith("oldv_") and k.endswith("_state"): # and int(request.form[k]) != 1:
                modvisits.append(k)

        for mv in modvisits:
            # extract and validate the id
            mvid = mv[5:-6]

            theVisit = VetInfo.query.filter_by(id=mvid).first();
            if not theVisit:
                return render_template("error_page.html", user=current_user, errormessage="planned visit not found (invalid id)", FAids=FAidSpecial)

            # make sure it's related to this cat
            if theVisit.cat_id != theCat.id:
                return render_template("error_page.html", user=current_user, errormessage="visit/cat id mismatch", FAids=FAidSpecial)

            # generate the form name prefix
            prefix = "oldv_"+mvid
            vv_updated = False

            # if deleted, delete immediately
            if int(request.form[prefix+"_state"]) == 2:
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} annullée".format(current_user.FAname, theVisit.vtype))
                db.session.add(theEvent)
                db.session.delete(theVisit)
                continue

            # modify the visit with the new data (we'll need to get all of it....)
            # if all reasons have been removed, erase it
            VisitType = vetMapToString(request.form, prefix)

            if VisitType == "--------":
                # all reasons removed, erase this
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} annullée".format(current_user.FAname, theVisit.vtype))
                db.session.add(theEvent)
                db.session.delete(theVisit)
                continue

            # update the record
            if theVisit.vtype != VisitType:
                theVisit.vtype = VisitType
                vv_updated = True

            try:
                VisitDate = datetime.strptime(request.form[prefix+"_date"], "%d/%m/%y")
            except ValueError:
                VisitDate = datetime.now()

            if theVisit.vdate != VisitDate:
                theVisit.vdate = VisitDate
                vv_updated = True

            # validate the vet
            vet = next((x for x in VETlist if x.id==int(request.form[prefix+"_vet"])), None)

            if not vet:
                return render_template("error_page.html", user=current_user, errormessage="vet id is invalid", FAids=FAidSpecial)
            else:
                if theVisit.vet_id != vet.id:
                    theVisit.vet_id = vet.id
                    vv_updated = True

            if theVisit.comments != request.form[prefix+"_comments"]:
                theVisit.comments = request.form[prefix+"_comments"]
                vv_updated = True

            if int(request.form[prefix+"_state"]) != 1:
                # means it's not planned anymore
                theCat.vetshort = vetAddStrings(theCat.vetshort, VisitType)
                theVisit.planned = False
                cat_updated = True
                vv_updated = True
                et = "effectuee le"
            else:
                et = "re-planifiee pour le"

            if vv_updated:
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, VisitType, et, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)

        # end for mv in modvisits

        if cat_updated:
            theCat.lastop = datetime.now()
        current_user.FAlastop = datetime.now()
        db.session.commit()
        message = [ [0, "Informations mises a jour"] ]

        # if we stay on the page, regenerate it directly
        if cmd == "fa_modcatr":
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, msg=message, VETids=VETlist, FAids=FAidSpecial)

        session["pendingmessage"] = message
        return redirect(url_for('fapage'))

    if cmd == "fa_adopted":
        newFA = User.query.filter_by(id=FAidSpecial[0]).first()
        newFA.numcats += 1
        theCat.owner.numcats -= 1
        theCat.owner_id = newFA.id
        theCat.adoptable = False
        # erase any planned visit
        VetInfo.query.filter_by(cat_id=theCat.id, planned=True).delete()
        theCat.lastop = datetime.now()
        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} transféré dans les adoptés".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: donné aux adoptants".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('fapage'))

    if cmd == "fa_dead":
        newFA = User.query.filter_by(id=FAidSpecial[1]).first()
        newFA.numcats += 1
        theCat.owner.numcats -= 1
        theCat.owner_id = newFA.id
        theCat.adoptable = False
        # erase any planned visit
        VetInfo.query.filter_by(cat_id=theCat.id, planned=True).delete()
        theCat.lastop = datetime.now()
        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} transféré dans les décédés".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: indiqué décédé".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('fapage'))

    if cmd == "adm_putcat" and access == ACC_TOTAL:
        # cat information is not updated
        FAid = int(request.form["FAid"])
        # validate the id
        theFA = User.query.filter_by(id=FAid).first()

        if theFA and FAid != theCat.owner_id:
            # generate the event
            session["pendingmessage"] = [ [0, "Chat {} transféré chez {}".format(theCat.asText(), theFA.FAname)] ]
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré de {} a {}".format(current_user.FAname, theCat.owner.FAname, theFA.FAname))
            db.session.add(theEvent)
            # modify the FA
            theFA.numcats += 1
            theCat.owner.numcats -= 1
            theCat.owner_id = FAid
            theCat.lastop = datetime.now()
            # in order to make it easier to list the "planned visits", any visit which is PLANNED is transferred to the new owner
            # the idea is than that any VetInfo with planned=True and doneby_id matching the user ALWAYS corresponds to cats he owns
            # this doesn't affect the visits which were performed. and the events will reflect the reality of who planned the visit since they are static
            theVisits = VetInfo.query.filter(and_(VetInfo.cat_id == theCat.id, VetInfo.planned == True)).all()
            for v in theVisits:
                v.doneby_id = FAid

            current_user.FAlastop = datetime.now()
            db.session.commit()

        return redirect(url_for('fapage'))

    # this should never be reached
    # display info about a cat
#    return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter_by(FAisFA=True).all())
    return render_template("error_page.html", user=current_user, errormessage="command error (/cat)", FAids=FAidSpecial)


@app.route("/search", methods=["GET", "POST"])
@login_required
def searchpage():
    if not current_user.FAisADM and not current_user.FAisOV:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges", FAids=FAidSpecial)

    if request.method == "GET":
        # generate the search page
        max_regnum = db.session.query(db.func.max(Cat.regnum)).scalar()

        return render_template("search_page.html", user=current_user, FAids=FAidSpecial, maxreg=max_regnum)

    cmd = request.form["action"]

    if cmd == "adm_search":
        src_name = request.form["src_name"]
        src_regnum = request.form["src_regnum"]
        src_id = request.form["src_id"]

        # if they are all empty => complain
        if not src_name and not src_regnum and not src_id:
            message = [ [3, "Il faut indiquer au moins un critere de recherche!" ] ]
            return render_template("search_page.html", user=current_user, FAids=FAidSpecial, msg=message)

        session["otherMode"] = "special-search"
        session["searchFilter"] = src_name+";"+src_regnum+";"+src_id
        return redirect(url_for('fapage'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/search)", FAids=FAidSpecial)


@app.route("/refu", methods=["GET", "POST"])
@login_required
def refupage():
    if not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges", FAids=FAidSpecial)

    if request.method == "GET":
        # generate the empty page with random filtering (for now)
        mdate = datetime.now() + timedelta(days=-7)
        cats = Cat.query.filter(Cat.lastop>=mdate).all()
        return render_template("refu_page.html", user=current_user, mdate=mdate, modcats=cats, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    cmd = request.form["action"]

    if cmd == "adm_modfilter":
        try:
            mdate = datetime.strptime(request.form["mod_date"], "%d/%m/%y")
        except ValueError:
            mdate = datetime.now()

        cats = Cat.query.filter(Cat.lastop>=mdate).all()
        return render_template("refu_page.html", user=current_user, mdate=mdate, modcats=cats, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    if cmd == "adm_refuexport":
#        return jsonify(request.form.to_dict())

        # this is potentially dangerous, if someone messes with the date, does not filter and then exports
        # but the only consequence is missing data, so I don't care
        try:
            mdate = datetime.strptime(request.form["mod_date"], "%d/%m/%y")
        except ValueError:
            mdate = datetime.now()

        cats = Cat.query.filter(Cat.lastop>=mdate).order_by(Cat.regnum).all()

        datfile = []

        for cat in cats:
            if "re_{}".format(cat.id) in request.form:
                comments = cat.comments.replace("\r",'')
                comments = comments.replace("\n","<EOL>")

                faname = cat.owner.username if not cat.owner_id == FAidSpecial[4] else "[{}]".format(cat.temp_owner)

                datline = [ cat.regStr(), faname, cat.name, cat.identif, DBTabSex[cat.sex],
                            ("" if not cat.birthdate else cat.birthdate.strftime('%d/%m/%y') ),
                            DBTabHair[cat.longhair], DBTabColor[cat.color], comments]

                for vv in cat.vetvisits:
                    datline.extend([ ("VP" if vv.planned else "VE"), vv.vtype, vv.vdate.strftime('%d/%m/%y'), str(vv.vet_id), vv.doneby.username ])

                datline.append("EOD")

                datfile.append(";".join(datline))

        return Response(
            "\n".join(datfile),
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=faweb-export.dat"})

    if cmd == "adm_refuexpall":
        # filter out --historique--???
        cats = Cat.query.order_by(Cat.regnum).all()

        datfile = []

        for cat in cats:
            comments = cat.comments.replace("\r",'')
            comments = comments.replace("\n","<EOL>")

            faname = cat.owner.username if not cat.owner_id == FAidSpecial[4] else "[{}]".format(cat.temp_owner)

            datline = [ cat.regStr(), faname, cat.name, cat.identif, DBTabSex[cat.sex],
                        ("" if not cat.birthdate else cat.birthdate.strftime('%d/%m/%y') ),
                        DBTabHair[cat.longhair], DBTabColor[cat.color], comments]

            for vv in cat.vetvisits:
                datline.extend([ ("VP" if vv.planned else "VE"), vv.vtype, vv.vdate.strftime('%d/%m/%y'), str(vv.vet_id), vv.doneby.username ])

            datline.append("EOD")

            datfile.append(";".join(datline))

        return Response(
            "\n".join(datfile),
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=faweb-dbase.dat"})

    if cmd == "adm_refuimport":
        # iterate on all the lines one by one
        # if a registre already exists, skip it (no update)
        msg = [ [1, "Resultats de l'import" ] ]

        if "r_dossier" in request.form:
            lines = request.form["r_dossier"].splitlines()

            for l in lines:
                v = l.split(';')

                if len(v) < 9:
                    msg.append([3, "Format erroné: {} (len={})".format(l, len(v)) ])
                    continue

                # if the regnum starts with * then it means we are editing an existing cat
                # in this case information is not completed, it's overwritten and vet visits
                # are edited as well
                editmode = False
                registre = v[0]
                if registre[0] == '*':
                    editmode = True
                    registre = registre[1:]

                # check if registre exists
                rr = registre.split('-')
                rn = int(rr[0]) + 10000*int(rr[1])

                # extract all the non-vet info so that we can update empty fields
                r_name = v[2]
                r_id = v[3]

                # convert fields to DB format (sex/hairlength/color)
                r = [index for index, value in enumerate(DBTabSex) if value == v[4]]
                if r:
                    r_sex = r[0]
                else:
                    r_sex = 0

                r = [index for index, value in enumerate(DBTabHair) if value == v[6]]
                if r:
                    r_hl = r[0]
                else:
                    r_hl = 0

                r = [index for index, value in enumerate(DBTabColor) if value == v[7]]
                if r:
                    r_col = r[0]
                else:
                    r_col = 0

                # convert birthdate
                try:
                    r_bd = datetime.strptime(v[5], "%d/%m/%y")
                except ValueError:
                    r_bd = None

                r_comm = v[8].replace("<EOL>", "\n")

                # see if we already have this
                theCat = Cat.query.filter_by(regnum=rn).first();

                # locate the FA, using the username
                # note that editmode can work with special FAs
                # we also handle the special case of temp FAs (recognized by the '[]' around the name)
                faname = v[1];
                temp_faname = ''
                if faname and faname[0] == '[' and faname[-1] == ']':
                    # temp fa
                    theFA = User.query.filter_by(id=FAidSpecial[4]).first()
                    temp_faname = faname[1:-1]
                else:
                    # normal (or special) FA
                    if editmode:
                        theFA = User.query.filter_by(username=faname).first()
                    else:
                        theFA = User.query.filter(and_(User.username==faname, or_(User.FAisFA==True,User.FAisREF==True))).first()

                # make sure that we have the FA
                if not theFA:
                    if editmode:
                        # assume it's the old one, in any case it's not like we can edit anything....
                        if faname:
                            # this means we wanted to move it, but the FA doesn't exist
                            msg.append([2, "{}: FA '{}' inexistente, le chat va rester dans la famille actuelle".format(registre, faname)])

                        theFA = theCat.owner

                    else:
                        # we need to define a FA, so we use the current user
                        msg.append([2, "{}: FA '{}' non trouvée, rajoute ici".format(registre, v[1]) ])
                        theFA = current_user

                # decode the table of vet visits
                offs = 9
                vvisits = []
                formaterror = False
                r_vetshort = '--------'

                while (v[offs] and v[offs] != 'EOD'):
                    if offs+5 > len(v):
                        msg.append([3, "Format erroné: {} (truncated vet info at offs {})".format(l, offs) ])
                        formaterror = True
                        break

                    v_planned = (v[offs] == 'VP')
                    v_type = v[offs+1]
                    # convert date
                    try:
                        v_date = datetime.strptime(v[offs+2], "%d/%m/%y")
                    except ValueError:
                        msg.append([3, "Format erroné: {} (invalid vdate at offs {})".format(l, offs) ])
                        formaterror = True
                        break

                    v_id = int(v[offs+3])
                    # validate vet id
                    vet = User.query.filter(and_(User.id==v_id,User.FAisVET==True)).first()
                    if not vet:
                        msg.append([3, "Format erroné: {} (invalid vet_id at offs {})".format(l, offs) ])
                        formaterror = True
                        break

                    # this is a complete mess, since there's no way to know WHICH FA has done the visit
                    # if the line specifies 'FA' we use the current (new FA)
                    # in all other cases AND for temporary FAs, we use the REF
                    v_doneby = FAidSpecial[3]
                    if v[offs+4] == 'FA' and not theFA.id == FAidSpecial[4]:
                        v_doneby = theFA.id

                    # all is good, cumulate vetinfo and prepare the object, cat_id will be invalid for now
                    if not v_planned:
                        r_vetshort = vetAddStrings(r_vetshort, v_type)

                    vvisits.append( VetInfo(doneby_id=v_doneby, vet_id=v_id, vtype=v_type, vdate=v_date, planned=v_planned) )
                    offs += 5

                # in case of format error, do nothing except spitting out the error message
                if formaterror:
                    continue

                # we now operate in two completely different ways depending if the cat is already in the
                # database or not and we are in edit mode or not

                if theCat == None and editmode:
                    msg.append([3, "Tentatif de mise a jour du {}, qui N'EST PAS dans la base de donnees!".format(registre) ])
                    continue

                if theCat != None and editmode:
                    # ok, we update the info here

                    # NOTE: in edit mode an empty fields means "leave data alone" and does not mean "erase data"
                    # info is Adopt Name Ident Sex Birthdate L(hairlen) Color (c)omments Description Picture
                    updated = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-']

                    if r_name and theCat.name != r_name:
                        theCat.name = r_name
                        updated[1] = 'N'

                    if r_id and theCat.identif != r_id:
                        theCat.identif = r_id
                        updated[2] ='I'

                    if r_sex and theCat.sex != r_sex:
                        theCat.sex = r_sex
                        updated[3] = 'S'

                    if r_bd and theCat.birthdate != r_bd:
                        theCat.birthdate = r_bd
                        updated[4] = 'B'

                    if r_hl and theCat.longhair != r_hl:
                        theCat.longhair = r_hl
                        updated[5] = 'L'

                    if r_col and theCat.color != r_col:
                        theCat.color = r_col
                        updated[6] = 'C'

                    if r_comm and theCat.comments != r_comm:
                        theCat.comments = r_comm
                        updated[7] = 'c'

                    # indicate moodification of the data
                    updated = "".join(updated)

                    if updated != "----------":
                        msg.append([1, "Numéro de registre {} mis a jour: {}".format(registre, updated)])
                        theCat.lastop = datetime.now()

                        # generate an event
                        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: informations mises a jour (Refugilys): {}".format(current_user.FAname, updated))
                        db.session.add(theEvent)

                    # update the FA if modified (note that here theFA is always defined!)
                    if faname:
                        msg.append([0, "Numéro de registre {} deplace de {} vers {}{}".format(registre, theCat.owner.FAname, theFA.FAname, faname if theFA.id == FAidSpecial[4] else '') ])
                        theCat.lastop = datetime.now()

                        # generate an event
                        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: FA mise a jour (Refugilys): {} -> {}".format(current_user.FAname, theCat.owner.FAname, theFA.FAname))
                        db.session.add(theEvent)

                        # update the FA by moving the cat
                        theCat.owner.numcats -= 1
                        theCat.owner_id = theFA.id
                        theFA.numcats += 1

                        # if we are moving TO a tempFA, update the name
                        if theFA.id == FAidSpecial[4]:
                            theCat.temp_owner = temp_faname

                        # if the destination FA is any of dead/adopted/historical then clear the adopted flag
                        if theFA.id == FAidSpecial[0] or theFA.id == FAidSpecial[1] or theFA.id == FAidSpecial[2]:
                            theCat.adoptable = False

                    # associate the vet visits
                    for vv in vvisits:
                        vv.cat_id = theCat.id
                        db.session.add(vv)

                    if r_vetshort != '--------':
                        msg.append([0, "Numéro de registre {} mis a jour: visites {}".format(registre, r_vetshort)])
                        theCat.vetshort = vetAddStrings(theCat.vetshort, r_vetshort)
                        theCat.lastop = datetime.now()
                        # generate an event
                        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: Visites mises a jour (Refugilys): {}".format(current_user.FAname, r_vetshort))
                        db.session.add(theEvent)

                    # should be done only if we updated something?
                    db.session.commit()
                    continue

                # if we reach here then editmode == False
                if theCat != None:
                    # this is update mode, vet data is ignored but any missing information which is available
                    # in the input is used to update the database

                    # info is Adoppt Name Ident Sex Birthdate L(hairlen) Color (c)omments Description Picture
                    updated = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-']

                    # note that only some data can be updated (adopt/desc/vetinfo can't, for example)
                    if not theCat.name and r_name:
                        theCat.name = r_name
                        updated[1] = 'N'

                    if not theCat.identif and r_id:
                        theCat.identif = r_id
                        updated[2] ='I'

                    if not theCat.sex and r_sex:
                        theCat.sex = r_sex
                        updated[3] = 'S'

                    if not theCat.birthdate and r_bd:
                        theCat.birthdate = r_bd
                        updated[4] = 'B'

                    if not theCat.longhair and r_hl:
                        theCat.longhair = r_hl
                        updated[5] = 'L'

                    if not theCat.color and r_col:
                        theCat.color = r_col
                        updated[6] = 'C'

                    if not theCat.comments and r_comm:
                        theCat.comments = r_comm
                        updated[7] = 'c'

                    # indicate moodification of the data
                    updated = "".join(updated)

                    if updated != "----------":
                        msg.append([2, "Numéro de registre {} déjà présent, informations rajoutees: {}".format(registre, updated)])
                        db.session.commit()
                    else:
                        msg.append([2, "Numéro de registre {} déjà présent, aucune nouvelle information, dossier ignoré".format(registre) ])

                    if not theFA:
                        msg.append([3, "Numéro de registre {} déjà présent et FA '{}' non trouvee!".format(registre, v[1]) ])
                    else:
                        if theCat.owner_id != theFA.id:
                            msg.append([3, "Numéro de registre {} déjà présent mais dans une autre FA (il est chez {}, on veut le rajouter chez {})!".format(registre, theCat.owner.FAname, theFA.FAname) ])
                    continue

                # now take care of the vetvisits
                # create the cat
                theCat = Cat(regnum=rn, owner_id=theFA.id, temp_owner=temp_faname, name=r_name, sex=r_sex, birthdate=r_bd, color=r_col, longhair=r_hl, identif=r_id,
                        vetshort=r_vetshort, comments=r_comm, description='', adoptable=False)

                db.session.add(theCat)
                theFA.numcats += 1

                # make sure we have an id
                db.session.commit()

                # associate the vet visits
                for vv in vvisits:
                    vv.cat_id = theCat.id
                    db.session.add(vv)

                # generate the event
                msg.append( [0, "Chat {} importé de Refugilys chez {}".format(registre, theFA.FAname) ] )
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: importé de Refugilys".format(current_user.FAname))
                db.session.add(theEvent)

        current_user.FAlastop = datetime.now()
        db.session.commit()

        session["pendingmessage"] = msg
        return redirect(url_for('fapage'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/refu)", FAids=FAidSpecial)
#    return redirect(url_for('refupage'))


@app.route("/vet", methods=["GET", "POST"])
@login_required
def vetpage():
    if request.method == "GET":
        return redirect(url_for('fapage'))

    cmd = request.form["action"]

    # this is a workaround to allow the 1st menu to return to the main view using a single form
    if cmd == "fa_catlist":
        # just return to the default main page
        session["otherMode"] = None
        return redirect(url_for('fapage'))

    if cmd == "fa_vetreg":
        # query all vetinfo which was doneby the FA
        FAid = current_user.id
        if "otherFA" in session:
            FAid = session["otherFA"]
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if not faexists:
                return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

            if theFA.FAresp_id != current_user.id and not (current_user.FAisOV or current_user.FAisADM):
                FAid = current_user.id

        theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==False)).order_by(VetInfo.vdate).all()

        if FAid != current_user.id:
            return render_template("regsoins_page.html", user=current_user, otheruser=theFA, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

        return render_template("regsoins_page.html", user=current_user, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    if cmd == "fa_vetplan":
        session["otherMode"] = "special-vetplan"
        return redirect(url_for('fapage'))

    if cmd == "fa_vetmv" or cmd == "fa_vetmvd":
        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): invalid vetinfo id", FAids=FAidSpecial)

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if not (theCat.owner_id == current_user.id and current_user.FAisFA) and not (theCat.owner.FAresp_id == current_user.id) and not current_user.FAisADM:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): insufficient privileges", FAids=FAidSpecial)

                # convert the visit to "effectuee" and log the event
                theCat.vetshort = vetAddStrings(theCat.vetshort, theVisit.vtype)
                theVisit.planned = False

                if cmd == "fa_vetmvd":
                    try:
                        theVisit.vdate = datetime.strptime(request.form["c_vdate"], "%d/%m/%y")
                    except ValueError:
                        theVisit.vdate = datetime.now()

                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} effectuée le {} chez {}".format(current_user.FAname, theVisit.vtype, theVisit.vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)
                db.session.commit()

        # return to the same page
        return redirect(url_for('fapage'))

    if cmd == "fa_vetmpl":
        FAid = current_user.id
        if "otherFA" in session:
            FAid = session["otherFA"]
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if not faexists:
                return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

            # permissions: ADM and OV see all
            # RF can see the ones they manage + adopt/dead/refuge
            if not (current_user.FAisRF and theFA.FAresp_id != current_user.id) and not (current_user.FAisRF and (FAid == FAidSpecial[0] or
                        FAid == FAidSpecial[1] or FAid == FAidSpecial[3])) and not (current_user.FAisOV or current_user.FAisADM):
                FAid = current_user.id

        VETlist = User.query.filter_by(FAisVET=True).all()

        if FAid != current_user.id:
            return render_template("vet_page.html", user=current_user, otheruser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                cats=Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all(), FAids=FAidSpecial, VETids=VETlist)

        return render_template("vet_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
            cats=Cat.query.filter_by(owner_id=current_user.id).order_by(Cat.regnum).all(), FAids=FAidSpecial, VETids=VETlist)


    if cmd == "fa_vetmpl_save":
        # vet list will be needed
        VETlist = User.query.filter_by(FAisVET=True).all()

        # start by decoding the visit data
        # generate the vetinfo record, if any, and the associated event
        VisitType = vetMapToString(request.form, "visit")

        if VisitType != "--------":
            # validate the vet
            vet = next((x for x in VETlist if x.id==int(request.form["visit_vet"])), None)

            if not vet:
                return render_template("error_page.html", user=current_user, errormessage="vet id is invalid", FAids=FAidSpecial)
            else:
                vetId = vet.id

            try:
                VisitDate = datetime.strptime(request.form["visit_date"], "%d/%m/%y")
            except ValueError:
                VisitDate = datetime.now()

            VisitPlanned = (int(request.form["visit_state"]) == 1)

            # if executed, then cumulate with the global
            if not VisitPlanned:
                et = "effectuee le"
            else:
                et = "planifiee pour le"
        else:
            session["pendingmessage"] = [ [ 2, "Aucun soin indique" ] ]
            return redirect(url_for('fapage'))

        # now iterate on all cats and add the visit
        catregs = []

        for key in request.form.keys():
            if key[0:3] == 're_':
                catid = int(key[3:])

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=catid).first()

                if not theCat:
                    return render_template("error_page.html", user=current_user, errormessage="fa_vetmpl_save: invalid cat id {}".format(catid), FAids=FAidSpecial)

                if not (theCat.owner_id == current_user.id and current_user.FAisFA) and not (theCat.owner.FAresp_id == current_user.id) and not current_user.FAisADM:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): insufficient privileges", FAids=FAidSpecial)

                catregs.append(theCat.regStr())

                # generate the visit and the event
                # we always associate the visit to the current owner
                theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vetId, vtype=VisitType, vdate=VisitDate,
                    planned=VisitPlanned, comments=request.form["visit_comments"])
                db.session.add(theVisit)
                db.session.commit()  # needed for vet.FAname

                # add it as event (planned or not)
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, VisitType, et, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)
                db.session.commit()

        if not catregs:
            session["pendingmessage"] = [ [ 2, "Aucun chat selectionne" ] ]
        else:
            session["pendingmessage"] = [ [ 0, "Visite {} enregistree pour les chats: {}".format(VisitType, ", ".join(catregs)) ] ]

        # return to vet page
        return redirect(url_for('fapage'))

    if cmd == "fa_vetbon":
        # generate the data for the bon
        catlist = []
        catregs = []
        theFA = None
        # vaccinations, rappels, sterilisations, castrations, identifications, tests fiv/felv, soins
        # if vtype is "soins" then we append the comment as visit description
        vtypes = [0, 0, 0, 0, 0, 0, 0]
        vdate = None
        comments = []
        # the QR code contains: ERA;<who authorized>;<today's date>;<FAid>;<visit date>;<cat regs>;<vtypes joined as string>;<check>
        # check is a 12-byte string obtained by md5sum of previous part + some random junk + base64_encode + cut in half

        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): invalid vetinfo id", FAids=FAidSpecial)

                if not vdate:
                    vdate = theVisit.vdate

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if not (theCat.owner_id == current_user.id and current_user.FAisFA) and not (theCat.owner.FAresp_id == current_user.id) and not current_user.FAisADM:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): insufficient privileges", FAids=FAidSpecial)

                if not theFA:
                    theFA = theCat.owner

                # cumulate the information
                catlist.append(theCat)
                catregs.append(theCat.regStr())

                if theVisit.vtype[0] != '-':
                    vtypes[0] += 1
                if theVisit.vtype[1] != '-':
                    vtypes[1] += 1
                if theVisit.vtype[2] != '-':
                    vtypes[1] += 1
                if theVisit.vtype[3] != '-':
                    if theCat.sex == 2:
                        vtypes[3] += 1
                    else:
                        vtypes[2] += 1
                if theVisit.vtype[4] != '-':
                    vtypes[4] += 1
                if theVisit.vtype[5] != '-':
                    vtypes[5] += 1
                if theVisit.vtype[6] != '-':
                    comments.append(theVisit.comments)
                    vtypes[6] += 1
                if theVisit.vtype[7] != '-':
                    vtypes[1] += 1

        # if nothing was selected, stay here
        if not catlist:
            session["pendingmessage"] = [ [ 2, "Aucune visite selectionnee" ] ]
            return redirect(url_for('fapage'))

        bdate = datetime.today()

        # generate the qrcode string
        qrstr = "ERA;{};{};{};{};{};{};".format(current_user.FAid, bdate.strftime('%Y%m%d'), theFA.FAid, vdate.strftime('%Y%m%d'), "/".join(catregs), "".join(str(e) for e in vtypes))
        qrstr = qrstr + ERAsum(qrstr)

        return render_template("bonveto_page.html", user=current_user, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, cats=catlist, fa=theFA, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    if cmd == "adm_vbver":
        bvcode = request.form["vb_qrcode"]

        if not bvcode:
            session["pendingmessage"] = [ [ 2, "Aucune code a verifier" ] ]
            return redirect(url_for('fapage'))

        if len(bvcode) > 15 and ERAsum(bvcode[0:-12]) == bvcode[-12:]:
            session["pendingmessage"] = [ [ 0, "Le code fourni est valable" ] ]
        else:
            session["pendingmessage"] = [ [ 3, "Le code fourni n'est PAS valable!" ] ]

        return redirect(url_for('fapage'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/vet)", FAids=FAidSpecial)


@app.route("/list", methods=["GET", "POST"])
@login_required
def listpage():
    if request.method == "GET":
        return redirect(url_for('fapage'))

    cmd = request.form["action"]

    if (cmd == "sv_viewFA" and (current_user.FAisADM or current_user.FAisOV)) or (cmd == "sv_viewFAresp" and (current_user.FAisRF)):
        # special FA we want some data from
        REFfa=User.query.filter_by(FAisREF=True).first()

        # prepare the table of the RFs
        RFlist=User.query.filter_by(FAisRF=True).all()

        RFtab = {}
        for rf in RFlist:
            RFtab[rf.id] = rf.FAname

        # get the correct list of FAs
        if cmd == "sv_viewFA":
            FAlist=User.query.filter_by(FAisFA=True).order_by(User.FAid).all()
        else: # cmd == "sv_viewFAresp"
            FAlist=User.query.filter_by(FAresp_id=current_user.id).order_by(User.FAid).all()

        return render_template("list_page.html", user=current_user, falist=FAlist, rftab=RFtab, refugfa=REFfa, FAids=FAidSpecial)

#    if cmd == "sv_viewFAresp" and (current_user.FAisRF):
        # special FA we want some data from
#        REFfa=User.query.filter_by(FAisREF=True).first()

        # all FAs we take care of (we assume they are FAs....)

#        return render_template("list_page.html", user=current_user, falist=FAlist, refugfa=REFfa, FAids=FAidSpecial)

    if cmd == "sv_globalTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats
        session["otherMode"] = "special-all"
        return redirect(url_for('fapage'))

    if cmd == "sv_adoptTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats with adoptable=true
        session["otherMode"] = "special-adopt"
        return redirect(url_for('fapage'))

    # default is indicate error
    return render_template("error_page.html", user=current_user, errormessage="command error (/list)", FAids=FAidSpecial)


@app.route("/user", methods=["GET", "POST"])
@login_required
def userpage():
    if not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access user data", FAids=FAidSpecial)

    # prepare the table of the RFs
    RFlist=User.query.filter_by(FAisRF=True).all()

    RFtab = {}
    for rf in RFlist:
        RFtab[rf.id] = rf.FAname

    if request.method == "GET" or (request.method == "POST" and request.form["action"] == "adm_listusers"):
        # normal users
        FAlist=User.query.order_by(User.FAid).all()

        # handle any message
        if "pendingmessage" in session:
            message = session["pendingmessage"]
            session.pop("pendingmessage")
        else:
            message = []

        return render_template("user_page.html", user=current_user, falist=FAlist, rftab=RFtab, FAids=FAidSpecial, msg=message)

    # user operations
    cmd = request.form["action"]

    if cmd == "adm_newuser":
        # generate an empty page to create a new user
        theFA = User()
        return render_template("user_page.html", user=current_user, fauser=theFA, rftab=RFtab, FAids=FAidSpecial)

    if cmd == "adm_adduser":
        # add a new user
        uname = request.form["u_username"].strip()
        if not uname:
            session["pendingmessage"] = [ [3, "Nom d'utilisateur vide" ] ]
            return redirect(url_for('userpage'))

        # check that it doesn't already exist
        faexists = db.session.query(User.id).filter_by(username=uname).scalar() is not None

        if faexists:
            session["pendingmessage"] = [ [3, "Nom d'utilisateur '{}' déjà utilisé!".format(uname) ] ]
            return redirect(url_for('userpage'))

        theFA = User(username=uname, password_hash="nologin", FAname=request.form["u_iname"], FAid=request.form["u_pname"], FAemail=request.form["u_email"],
                     numcats=0, FAisFA=("u_isFA" in request.form), FAisRF=("u_isRF" in request.form),
                     FAisOV=("u_isOV" in request.form), FAisVET=("u_isVET" in request.form) )

        theFA.FAresp_id = int(request.form["u_resp"])
        # sanity check
        if not theFA.FAresp_id or theFA.FAisRF or theFA.FAisADM:
            theFA.FAresp_id = None

        db.session.add(theFA)
        db.session.commit()

        session["pendingmessage"] = [ [0, "Nouveau utilisateur '{}' creé sans mot de passe".format(theFA.username) ] ]
        return redirect(url_for('userpage'))

    # edit existing user
    theFA = User.query.filter_by(id=request.form["FAid"]).first()

    if not theFA:
        return render_template("error_page.html", user=current_user, errormessage="invalid used id", FAids=FAidSpecial)

    if cmd == "adm_edituser":
        return render_template("user_page.html", user=current_user, fauser=theFA, rftab=RFtab, FAids=FAidSpecial)

    if cmd == "adm_moduser":
        theFA.FAid = request.form["u_pname"]
        theFA.FAname = request.form["u_iname"]
        theFA.FAemail = request.form["u_email"]
        theFA.FAresp_id = int(request.form["u_resp"]) if "u_resp" in request.form else 0
        theFA.FAisFA = "u_isFA" in request.form;
        theFA.FAisRF = "u_isRF" in request.form;
        theFA.FAisOV = "u_isOV" in request.form;
        theFA.FAisVET = "u_isVET" in request.form;

        # sanity check
        if not theFA.FAresp_id or theFA.FAisRF or theFA.FAisADM:
            theFA.FAresp_id = None

        db.session.commit()
        session["pendingmessage"] = [ [0, "Utilisateur {} : informations mises à jour".format(theFA.username) ] ]
        return redirect(url_for('userpage'))

    if cmd == "adm_pwduser":
        # note: CANNOT be done for adm users, this must be done manually, unless it's yourself
        if theFA.id != current_user.id and theFA.FAisADM:
            session["pendingmessage"] = [ [2, "Impossible de modifier le MDP d'un autre GR"] ]
            return redirect(url_for('userpage'))

        # generate a new random password
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for i in range(8))

        theFA.password_hash = generate_password_hash(password)
        db.session.commit()

        session["pendingmessage"] = [ [0, "Nouveau mot de passe pour {} : {}".format(theFA.username, password) ] ]
        return redirect(url_for('userpage'))

    # default is indicate error
    return render_template("error_page.html", user=current_user, errormessage="command error (/user)", FAids=FAidSpecial)


def exportCSV(catlist):
    csv="FA,Registre,Puce,Nom,Sexe,Date Naissance,Couleur,Poil,Veterinaire,Adoptable,Commentaires\n"

    for cat in catlist:
        # historical cats are ignored
        if cat.owner.FAisHIST:
            continue

        # this is looking for trouble.....
        cdesc = cat.comments
        cdesc.replace('"', '""')

        csv += ('"'+cat.owner.FAname+'",'+cat.regStr()+','+cat.identif+',"'+cat.name+'",'+
            TabSex[cat.sex]+','+(cat.birthdate.strftime("%d/%m/%y") if cat.birthdate else '')+','+TabColor[cat.color]+','+
            TabHair[cat.longhair]+','+cat.vetshort+','+('Adoptable' if cat.adoptable else '')+',"'+cdesc+'"\n')

    return csv


@app.route("/listcsv")
@login_required
def listdownload():
    if current_user.FAisADM or current_user.FAisOV:
        # generate the global table as CSV file
        catlist=Cat.query.all()

        csv = exportCSV(catlist)

        current_user.FAlastop = datetime.now()
        db.session.commit()

        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=chatsFA.csv"})

    # default is return to index
    return redirect(url_for('fapage'))


@app.route("/listcsva")
@login_required
def listadownload():
    if current_user.FAisADM or current_user.FAisOV:
        # generate the table as CSV file
        catlist=Cat.query.filter_by(adoptable=True).all()

        csv = exportCSV(catlist)

        current_user.FAlastop = datetime.now()
        db.session.commit()

        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=adoptables.csv"})

    # default is return to index
    return redirect(url_for('fapage'))


@app.route("/help")
@login_required
def helppage():
    return render_template("help_page.html", user=current_user, FAids=FAidSpecial)


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

    # store last access and fix number of cats (just in case...)
    ncats = Cat.query.filter_by(owner_id=current_user.id).count()
    if ncats != current_user.numcats:
        current_user.numcats = ncats

    current_user.FAlastop = datetime.now()
    db.session.commit()

    return redirect(url_for('fapage'))

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('fapage'))
