
# ERA FA management flask app

# jsonify is for debugging
from flask import Flask, render_template, redirect, request, url_for, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
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


# --------------- STATIC DATA

# this maps DB field number to the string
# NOTE they must match the ones used in cat_page.html
DBTabColor = ["INCONNU", "BEIGE", "BEIGE ET BLANC", "BLANC", "BLUE POINT", "CREME", "ECAILLE DE TORTUE", "GRIS", "GRIS CHARTREUX", "GRIS ET BLANC",
             "NOIR", "NOIR ET BLANC", "NOIR ET SMOKE", "NOIR PLASTRON BLANC", "ROUX", "ROUX ET BLANC", "SEAL POINT", "TABBY BLANC", "TABBY BRUN", "TABBY GRIS",
             "TIGRE", "TIGRE BEIGE", "TIGRE BRUN", "TIGRE CREME", "TIGRE GRIS", "TRICOLORE"]
DBTabSex = ["INCONNU", "FEMELLE", "MALE"]
DBTabHair = ["COURT", "MI-LONG", "LONG"]

# these are the readable (html page) versions
TabColor = ["??couleur??", "Beige", "Beige et blanc", "Blanc", "Blue point", "Creme", "Ecaille de tortue", "Gris", "Gris chartreux", "Gris et blanc",
             "Noir", "Noir et blanc", "Noir et smoke", "Noir plastron blanc", "Roux", "Roux et blanc", "Seal point", "Tabby blanc", "Tabby brun", "Tabby gris",
             "Tigré", "Tigré beige", "Tigré brun", "Tigré creme", "Tigré gris", "Tricolore"]
TabSex = ["??sexe??", "Femelle", "Male"]
TabHair = ["", ", poil mi-long", ", poil long"]


#TabHair = ["COURT", "MI-LONG", "LONG"]
# static since it changes rarely, NOTE: it must also be changed in cat_page.html
VETlist = [ [8, "Autre (commentaires)"], [ 6, "AMCB Veterinaires" ], [7, "Clinique Mont. Verte"]  ]

# special FA ids (static): AD DCD HIST
FAidSpecial = [2, 5, 10]

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
    for i in range(0,7):
        if str[i] == '-':
            str[i] = vetstr2[i]

    return "".join(str)

#
# --------------- DATABASE INITIALIZATION (required special FAs)
#
# > export FLASK_APP=flask_app.py
# > flask shell
# > from flask_app import db, User
# > newuserAD = User(username="--adopted--", password_hash="nologinAD", FAname="Chats adoptes", FAid="ADOPTIONS", FAemail="invalid@invalid", FAisFA=False, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=True, FAisDCD=False, FAisVET=False, FAisHIST=False)
# > newuserDCD = User(username="--decedes--", password_hash="nologinDCD", FAname="Chats decedes", FAid="DECES", FAemail="invalid@invalid", FAisFA=False, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=True, FAisVET=False, FAisHIST=False)
# > newuserHIST = User(username="--historique--", password_hash="nologinHIST", FAname="Chats: historique", FAid="HISTORIQUE", FAemail="invalid@invalid", FAisFA=False, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=True)
# > db.session.add(newuserAD)
# > db.session.add(newuserDCD)
# > db.session.add(newuserHIST)
# > db.session.commit()

# --------------- USER CLASS

# to create a new user:
# > export FLASK_APP=flask_app.py
# > flask shell
# > from flask_app import db, User
# > from werkzeug.security import generate_password_hash
# > newuser = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=False)
# > newuserFA = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=False)
# > newuserVET = User(username="login", password_hash=generate_password_hash("password"), FAname="VET name(long)", FAid="name(short)", FAemail="invalid@invalid", FAisFA=False, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=True, FAisHIST=False)
# > db.session.add(newuser)
# > db.session.commit()

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
    FAresp = db.relationship('User', foreign_keys=FAresp_id)
    FAisFA = db.Column(db.Boolean, nullable=False)
    FAisRF = db.Column(db.Boolean, nullable=False)
    FAisOV = db.Column(db.Boolean, nullable=False)
    FAisADM = db.Column(db.Boolean, nullable=False)
    FAisAD = db.Column(db.Boolean, nullable=False)
    FAisDCD = db.Column(db.Boolean, nullable=False)
    FAisVET = db.Column(db.Boolean, nullable=False)
    FAisHIST = db.Column(db.Boolean, nullable=False)
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

# --------------- CAT CLASS

# ORDER BY SUBSTR(registre....) e usando CHAR_LENGTH()

class Cat(db.Model):

    __tablename__ = "cats"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('User', foreign_keys=owner_id)
    name = db.Column(db.String(32))
    sex = db.Column(db.Integer)
    color = db.Column(db.Integer)
    longhair = db.Column(db.Integer)
    birthdate = db.Column(db.DateTime)
    registre = db.Column(db.String(8))
    identif = db.Column(db.String(16))
    description = db.Column(db.String(1024))
    vetshort = db.Column(db.String(16))
    adoptable = db.Column(db.Boolean)
    vetvisits = db.relationship('VetInfo', backref='cat', lazy=True)
    lastop = db.Column(db.DateTime)
    events = db.relationship('Event', backref='cat', lazy=True)

    def __repr__(self):
        return "<Cat {}>".format(self.registre)

    def asText(self):
        str = ""
        if self.name:
            str += self.name
        else:
            str += "pas de nom"

        str += "(" + self.registre

        if self.identif:
            str += "/"+self.identif+")"
        else:
            str += ")"

        return str


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

# --------------- EVENT CLASS

class Event(db.Model):

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    cat_id = db.Column(db.Integer, db.ForeignKey('cats.id'), nullable=False)
    edate = db.Column(db.DateTime, default=datetime.now)
    etext = db.Column(db.String(1024))



#class Comment(db.Model):
#
#    __tablename__ = "comments"
#
#    id = db.Column(db.Integer, primary_key=True)
#    content = db.Column(db.String(4096))
#    posted = db.Column(db.DateTime, default=datetime.now)
#    commenter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
#    commenter = db.relationship('User', foreign_keys=commenter_id)

# test page

@app.route('/misc')
@login_required
def miscpage():
    return render_template("misc_page.html", user=current_user)

# --------------- WEB PAGES

@app.route('/', methods=["GET", "POST"])
@app.route('/index', methods=["GET", "POST"])
def index():
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
            if (mode == "special-all" or mode == "special-adopt") and not (current_user.FAisOV or current_user.FAisADM):
                mode = None

        # display current user pages or alternate user's?
        # we can see pages of other FAs if we are OV/ADM or we are the FA's resp
        FAid = current_user.id
        if "otherFA" in session:
            FAid = session["otherFA"]
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if not faexists:
                return render_template("error_page.html", user=current_user, errormessage="invalid FA id")

            # check if we can see it
            if theFA.FAresp_id != current_user.id and not (current_user.FAisOV or current_user.FAisADM):
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
                catlist=Cat.query.all(), FAids=FAidSpecial, msg=message)

        elif mode == "special-adopt":
            return render_template("list_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                catlist=Cat.query.filter_by(adoptable=True).all(), FAids=FAidSpecial, msg=message, adoptonly=True)

        if FAid != current_user.id:
            return render_template("main_page.html", user=current_user, otheruser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                cats=Cat.query.filter_by(owner_id=FAid).all(), FAids=FAidSpecial, msg=message)

        return render_template("main_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
            cats=Cat.query.filter_by(owner_id=current_user.id).all(), FAids=FAidSpecial, msg=message)

    # handle POST commands
    cmd = request.form["action"]

    # alternate GET command for another FA
    if cmd == "sv_fastate":
        FAid = int(request.form["FAid"]);
        # note: we do not perform any check on the validity of FAid or on the access privileges,
        # since they will be performed by the GET method

        session["otherMode"] = None
        session["otherFA"] = FAid
        return redirect(url_for('index'))

    # get the cat
    theCat = Cat.query.filter_by(id=request.form["catid"]).first()
    if theCat == None:
        return render_template("error_page.html", user=current_user, errormessage="invalid cat id")
        return redirect(url_for('index'))

    # check if you can access this
    if theCat.owner_id != current_user.id and not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data")
        return redirect(url_for('index'))

    if cmd == "adm_histcat" and current_user.FAisADM:
        # move the cat to the historical list of cats
        theCat.owner_id = FAidSpecial[2]
        theCat.lastop = datetime.now()
        session["pendingmessage"] = [ [0, "Chat {} deplace dans l'historique".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: trasfere dans l'historique".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()

    if cmd == "adm_deletecat" and current_user.FAisADM:
        # erase the cat and all the associated information from the database
        # NOTE THAT THIS IS IRREVERSIBLE AND LEAVES NO TRACE
        session["pendingmessage"] = [ [0, "Chat {} efface du systeme".format(theCat.asText())] ]
        Event.query.filter_by(cat_id=theCat.id).delete()
        VetInfo.query.filter_by(cat_id=theCat.id).delete()
        db.session.delete(theCat)
        current_user.FAlastop = datetime.now()
        db.session.commit()

    return redirect(url_for('index'))


@app.route("/self")
@login_required
def selfpage():
    # a version of the main page which brings you back to your list
    session.pop("otherFA", None)
    session.pop("otherMode", None)
    return redirect(url_for('index'))


@app.route("/cat", methods=["POST"])
@login_required
def catpage():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    cmd = request.form["action"]

    if cmd == "fa_return":
        return redirect(url_for('index'))

    # generate an empty page for the addition of a Refu dossier
    if cmd == "adm_refucat" and current_user.FAisADM:
        return render_template("refu_page.html", user=current_user)

    # generate an empty page to add a new cat
    if cmd == "adm_newcat" and current_user.FAisADM:
        theCat = Cat(registre="")
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter_by(FAisFA=True).all())

    if (cmd == "adm_addcathere" or cmd == "adm_addcatputFA") and current_user.FAisADM:
        # generate the new cat using the form information
        vetstr = vetMapToString(request.form, "visit")

        try:
            bdate = datetime.strptime(request.form["c_birthdate"], "%d/%m/%y")
        except ValueError:
            bdate = None

        theCat = Cat(registre=request.form["c_registre"], name=request.form["c_name"], sex=request.form["c_sex"], birthdate=bdate,
                    color=request.form["c_color"], longhair=request.form["c_hlen"], identif=request.form["c_identif"],
                    description=request.form["c_description"], vetshort=vetstr, adoptable=(request.form["c_adoptable"]=="1"))

        # ensure that registre is unique
        checkCat = Cat.query.filter_by(registre=request.form["c_registre"]).first()

        if checkCat:
            # this is bad, we regenerate the page wit the current data
            message = [ [3, "Le numero de registre existe deja!"] ]
            theCat.registre = None
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter_by(FAisFA=True).all(), msg=message)

        # if for any reason the FA is invalid, then put it here
        if cmd != "adm_addcathere":
            FAid = int(request.form["FAid"]);
            # validate the id
            faexists = db.session.query(User.id).filter_by(id=FAid).scalar() is not None;

            if cmd == "adm_addcatputFA" and faexists:
                theCat.owner_id = FAid
            else:
                theCat.owner_id = current_user.id

        else: # cmd == "addcathere"
            theCat.owner_id = current_user.id

        db.session.add(theCat)
        # make sure we have an id
        db.session.commit()

        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} rajoute dans le systeme".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: rajoute dans le systeme".format(current_user.FAname))
        db.session.add(theEvent)

        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('index'))

    # existing cat, populate the page with the available data
    theCat = Cat.query.filter_by(id=request.form["catid"]).first();
    if theCat == None:
        return render_template("error_page.html", user=current_user, errormessage="invalid cat id")
        return redirect(url_for('index'))

    # if we're working on another user's cats, show the information on top of the page
    FAid = current_user.id
    access = ACC_NONE

    if "otherFA" in session:
        FAid = session["otherFA"]
        theFA = User.query.filter_by(id=FAid).first()
        faexists = theFA is not None;

        if not faexists:
            return render_template("error_page.html", user=current_user, errormessage="invalid FA id")

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
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data")

    if access == ACC_RO:
        # FAid != current_user.id is implied
        return render_template("cat_page.html", user=current_user, otheruser=theFA, cat=theCat, readonly=True)

    # if we reach here, we have ACC_FULL
    # some operations may still be unavailable!

    FAlist = []
    if access == ACC_TOTAL:
        FAlist = User.query.filter_by(FAisFA=True).all()

    # handle generation of the page
    if cmd == "fa_viewcat":
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist)

    # cat commands
    if cmd == "fa_modcat" or cmd == "fa_modcatr":
        # return jsonify(request.form.to_dict())

        # update cat information and indicate what was changed
        updated = ['-', '-', '-', '-', '-', '-', '-', '-']
        if theCat.name != request.form["c_name"]:
            theCat.name = request.form["c_name"]
            updated[1] = 'N'

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
            updated[5] = 'P'

        if theCat.identif != request.form["c_identif"]:
            theCat.identif=request.form["c_identif"]
            updated[2] = 'I'

        if theCat.description != request.form["c_description"]:
            theCat.description=request.form["c_description"]
            updated[7] = 'D'

        if theCat.adoptable != (request.form["c_adoptable"] == "1"):
            theCat.adoptable=(request.form["c_adoptable"] == "1")
            updated[0] = 'A'

        # indicate moodification of the data
        updated = "".join(updated)

        if updated != "--------":
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: mise a jour des informations {}".format(current_user.FAname, updated))
            db.session.add(theEvent)

        # generate the vetinfo record, if any, and the associated event
        VisitType = vetMapToString(request.form, "visit")

        if VisitType != "--------":
            # validate the vet
            vetId = next((x for x in VETlist if x[0]==int(request.form["visit_vet"])), None)

            if not vetId:
                return render_template("error_page.html", user=current_user, errormessage="vet id is invalid")
            else:
                vetId = vetId[0]

            try:
                VisitDate = datetime.strptime(request.form["visit_date"], "%d/%m/%y")
            except ValueError:
                VisitDate = datetime.now()

            VisitPlanned = (int(request.form["visit_state"]) == 1)

            # if executed, then cumulate with the global
            if not VisitPlanned:
                theCat.vetshort = vetAddStrings(theCat.vetshort, VisitType)

            theVisit = VetInfo(cat_id=theCat.id, doneby_id=FAid, vet_id=vetId, vtype=VisitType, vdate=VisitDate,
                planned=VisitPlanned, comments=request.form["visit_comments"])
            db.session.add(theVisit)
            db.session.commit()  # needed for vet.FAname

            # if not planned, add it as event
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite veterinaire {} planifiee pour le {} chez {}".format(current_user.FAname, VisitType, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
            db.session.add(theEvent)

        # iterate through all the planned visits and see if they have been updated....
        # extract all planned visits which are now executed
        modvisits = []
        for k in request.form.keys():
            if k.startswith("oldv_") and k.endswith("_state") and int(request.form[k]) != 1:
                modvisits.append(k)

        for mv in modvisits:
            # extract and validate the id
            mvid = mv[5:-6]

            theVisit = VetInfo.query.filter_by(id=mvid).first();
            if not theVisit:
                return render_template("error_page.html", user=current_user, errormessage="planned visit not found (invalid id)")

            # make sure it's related to this cat
            if theVisit.cat_id != theCat.id:
                return render_template("error_page.html", user=current_user, errormessage="visit/cat id mismatch")

            # generate the form name prefix
            prefix = "oldv_"+mvid

            # if deleted, delete immediately
            if int(request.form[prefix+"_state"]) == 2:
                db.session.delete(theVisit)
                continue

            # modify the visit with the new data (we'll need to get all of it....)
            # if all reasons have been removed, erase it
            VisitType = vetMapToString(request.form, prefix)

            if VisitType == "--------":
                # all reasons removed, erase this
                db.session.delete(theVisit)
                continue

            # update the record
            theVisit.VisitType = VisitType

            try:
                VisitDate = datetime.strptime(request.form[prefix+"_date"], "%d/%m/%y")
            except ValueError:
                VisitDate = datetime.now()
            theVisit.visitDate = VisitDate

            theVisit.planned = False

            # validate the vet
            vetId = next((x for x in VETlist if x[0]==int(request.form[prefix+"_vet"])), None)

            if not vetId:
                return render_template("error_page.html", user=current_user, errormessage="vet id is invalid")
            else:
                vetId = vetId[0]

            theVisit.comments = request.form[prefix+"_comments"]

            theCat.vetshort = vetAddStrings(theCat.vetshort, VisitType)

            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite veterinaire {} effectuee le {} chez {}".format(current_user.FAname, VisitType, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
            db.session.add(theEvent)

        # end for mv in modvisits

        theCat.lastop = datetime.now()
        current_user.FAlastop = datetime.now()
        db.session.commit()
        message = [ [0, "Informations mises a jour"] ]

        # if we stay on the page, regenerate it directly
        if cmd == "fa_modcatr":
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, msg=message)

        session["pendingmessage"] = message
        return redirect(url_for('index'))

    if cmd == "fa_adopted":
        theCat.owner_id = FAidSpecial[0]
        theCat.lastop = datetime.now()
        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} transfere dans les adoptes".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: donne aux adoptants".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('index'))

    if cmd == "fa_dead":
        theCat.owner_id = FAidSpecial[1]
        theCat.lastop = datetime.now()
        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} transfere dans les decedes".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: indique decede".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('index'))

    if cmd == "adm_putcat" and access == ACC_TOTAL:
        # cat information is not updated
        FAid = int(request.form["FAid"])
        # validate the id
        theFA = User.query.filter_by(id=FAid).first()

        if theFA and FAid != theCat.owner_id:
            # generate the event
            session["pendingmessage"] = [ [0, "Chat {} transfere chez {}".format(theCat.asText(), theFA.FAname)] ]
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transfere de {} a {}".format(current_user.FAname, theCat.owner.FAname, theFA.FAname))
            db.session.add(theEvent)
            # modify the FA
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

        return redirect(url_for('index'))

    # this should never be reached
    # display info about a cat
#    return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter_by(FAisFA=True).all())
    return render_template("error_page.html", user=current_user, errormessage="command error (/cat)")

@app.route("/refu", methods=["POST"])
@login_required
def addrefupage():
    if not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to add data")

    # iterate on all the lines one by one
    # if a registre already exists, skip it (no update)
    msg = [ [1, "Resultats de l'import" ] ]

    if "r_dossier" in request.form:
        lines = request.form["r_dossier"].splitlines()

        for l in lines:
            v = l.split(';')

            if len(v) != 10:
                msg.append([3, "Format erroné: {} (len={})".format(l, len(v)) ])
                continue

            # check if registre exists
            theCat = Cat.query.filter_by(registre=v[0]).first();
            if theCat != None:
                msg.append([3, "Numéro de registre {} déjà présent, dossier ignoré".format(v[0]) ])
                continue

            # locate the FA, using the username
            theFA = User.query.filter(and_(User.username==v[1], User.FAisFA==True)).first()

            if not theFA:
                msg.append([1, "{}: FA '{}' non trouvee, rajoute ici".format(v[0], v[1]) ])
                theFA = current_user

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

            r_comm = v[9].replace("<eol>", "\n")

            # create the cat
            theCat = Cat(registre=v[0], owner_id=theFA.id, name=v[2], sex=r_sex, birthdate=r_bd, color=r_col, longhair=r_hl, identif=v[3],
                    description=r_comm, vetshort=v[8], adoptable=False)
            db.session.add(theCat)
            # make sure we have an id
            db.session.commit()

            # generate the event
            msg.append( [0, "Chat {} rajoute chez {}".format(v[0], theFA.FAname) ] )
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: rajoute dans le systeme".format(current_user.FAname))
            db.session.add(theEvent)

    current_user.FAlastop = datetime.now()
    db.session.commit()

    session["pendingmessage"] = msg

    return redirect(url_for('index'))


@app.route("/vet", methods=["POST"])
@login_required
def vetpage():
    cmd = request.form["action"]

    if cmd == "fa_catlist":
        # just return to the default main page
        session["otherMode"] = None
        return redirect(url_for('index'))

    if cmd == "fa_vetreg":
        # query all vetinfo which was doneby the FA
        FAid = current_user.id
        if "otherFA" in session:
            FAid = session["otherFA"]
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if not faexists:
                return render_template("error_page.html", user=current_user, errormessage="invalid FA id")

            if theFA.FAresp_id != current_user.id and not (current_user.FAisOV or current_user.FAisADM):
                FAid = current_user.id

        theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==False)).order_by(VetInfo.vdate).all()

        if FAid != current_user.id:
            return render_template("regsoins_page.html", user=current_user, otheruser=theFA, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

        return render_template("regsoins_page.html", user=current_user, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    if cmd == "fa_vetplan":
        session["otherMode"] = "special-vetplan"
        return redirect(url_for('index'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/vet)")


@app.route("/list", methods=["POST"])
@login_required
def listpage():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    cmd = request.form["action"]

    if cmd == "sv_viewFA" and (current_user.FAisADM or current_user.FAisOV):
        # normal FAs
        FAlist=User.query.filter_by(FAisFA=True).all()

        return render_template("list_page.html", user=current_user, falist=FAlist, FAids=FAidSpecial)

    if cmd == "sv_viewFAresp" and (current_user.FAisRF):
        # all FAs we take care of (we assume they are FAs....)
        FAlist=User.query.filter_by(FAresp_id=current_user.id).all()

        return render_template("list_page.html", user=current_user, falist=FAlist, FAids=FAidSpecial)

    if cmd == "sv_globalTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats
        session["otherMode"] = "special-all"
        return redirect(url_for('index'))

    if cmd == "sv_adoptTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats with adoptable=true
        session["otherMode"] = "special-adopt"
        return redirect(url_for('index'))

    # default is return to index
    return render_template("error_page.html", user=current_user, errormessage="command error (/list)")


def exportCSV(catlist):
    csv="FA,Registre,Puce,Nom,Sexe,Date Naissance,Couleur,Poil,Veterinaire,Adoptable,Description\n"

    for cat in catlist:
        # historical cats are ignored
        if cat.owner.FAisHIST:
            continue

        # this is looking for trouble.....
        cdesc = cat.description
        cdesc.replace('"', '""')

        csv += ('"'+cat.owner.FAname+'",'+cat.registre+','+cat.identif+',"'+cat.name+'",'+
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
    return redirect(url_for('index'))


@app.route("/listcsva")
@login_required
def listadownload():
    if current_user.FAisADM or current_user.FAisOV:
        # generate the table as CSV file
        catlist=Cat.query.filter_by(adoptable=True).all()

        csv = exportCSV(catlist)
        db.session.commit()

        current_user.FAlastop = datetime.now()
        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=adoptables.csv"})

    # default is return to index
    return redirect(url_for('index'))


@app.route("/help")
@login_required
def helppage():
    return render_template("help_page.html", user=current_user)


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

    # store last access (NOT FOR NOW)
#    current_user.FAlastop = datetime.now()
#    db.session.commit()

    return redirect(url_for('index'))

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
