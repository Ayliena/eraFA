
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

# NOTE: it must also be changed in main_page.html and cat_page.html
TabColor = ["??couleur??", "Beige", "Beige et blanc", "Blanc", "Blue point", "Creme", "Ecaille de tortue", "Gris", "Gris chartreux", "Gris et blanc",
             "Noir", "Noir et blanc", "Noir et smoke", "Noir plastron blanc", "Roux", "Roux et blanc", "Seal point", "Tabby blanc", "Tabby brun", "Tabby gris",
             "Tigre", "Tigre beige", "Tigre brun", "Tigre creme", "Tigre gris", "Tricolore"]
TabSex = ["??sexe??", "Femelle", "Male"]
TabHair = ["", ", poil mi-long", ", poil long"]
#TabHair = ["COURT", "MI-LONG", "LONG"]
# static since it changes rarely, NOTE: it must also be changed in cat_page.html
VETlist = [ [8, "Autre (commentaires)"], [ 6, "AMCB Veterinaires" ], [7, "Clinique Mont. Verte"]  ]

# special FA ids (static): AD DCD HIST
FAidSpecial = [2, 5, 10]

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
# > newuserAD = User(username="--adopted--", password_hash="nologinAD", FAname="Chats adoptes", FAid="ADOPTIONS", FAemail="invalid@invalid", FAisFA=False, FAisOV=False, FAisADM=False, FAisAD=True, FAisDCD=False, FAisVET=False, FAisHIST=False)
# > newuserDCD = User(username="--decedes--", password_hash="nologinDCD", FAname="Chats decedes", FAid="DECES", FAemail="invalid@invalid", FAisFA=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=True, FAisVET=False, FAisHIST=False)
# > newuserHIST = User(username="--historique--", password_hash="nologinHIST", FAname="Chats: historique", FAid="HISTORIQUE", FAemail="invalid@invalid", FAisFA=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=True)
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
# > newuser = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=False)
# > newuserFA = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=False)
# > newuserVET = User(username="login", password_hash=generate_password_hash("password"), FAname="VET name(long)", FAid="name(short)", FAemail="invalid@invalid", FAisFA=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=True, FAisHIST=False)
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
    FAisFA = db.Column(db.Boolean, nullable=False)
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
            session["pendingmessage"] = None
        else:
            message = []

        # handle planned vet list
        if "otherMode" in session and session["otherMode"] == "special-vetplan":
            # query all vetinfo which are planned and associated with cats you own
            theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==current_user.id, VetInfo.planned==False)).order_by(VetInfo.vdate).all()

            return render_template("vet_page.html", user=current_user, visits=theVisits)

        # are we looking at a page from another FA?
        if "otherFA" in session and (current_user.FAisOV or current_user.FAisADM):
            FAid = session["otherFA"]

            # special lists?
            if FAid == "special-all":
                return render_template("list_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    catlist=Cat.query.all(), FAids=FAidSpecial, msg=message)

            if FAid == "special-adopt":
                return render_template("list_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    catlist=Cat.query.filter_by(adoptable=True).all(), FAids=FAidSpecial, msg=message, adoptonly=True)

            # validate the id
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if faexists:
                return render_template("main_page.html", user=current_user, otheruser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    cats=Cat.query.filter_by(owner_id=FAid).all(), FAids=FAidSpecial, msg=message)

        return render_template("main_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
            cats=Cat.query.filter_by(owner_id=current_user.id).all(), FAids=FAidSpecial, msg=message)
#            cats=current_user.cats, icats=current_user.icats)

    # handle commands
    cmd = request.form["action"]

    # alternate GET command for another FA
    if cmd == "sv_fastate" and (current_user.FAisOV or current_user.FAisADM):
        FAid = int(request.form["FAid"]);
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
        session["pendingmessage"] = [0, "Chat {} deplace dans l'historique".format(theCat.asText())]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: trasfere dans l'historique".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()

    if cmd == "adm_deletecat" and current_user.FAisADM:
        # erase the cat and all the associated information from the database
        # NOTE THAT THIS IS IRREVERSIBLE AND LEAVES NO TRACE
        session["pendingmessage"] = [0, "Chat {} efface du systeme".format(theCat.asText())]
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

    # prepare the list of FAs for transfers
    FAlist=User.query.filter_by(FAisFA=True).all()

    # generate an empty page for the addition of a Refu dossier
    if cmd == "adm_refucat" and current_user.FAisADM:
        return render_template("refu_page.html", user=current_user)

    # generate an empty page to add a new cat
    if cmd == "adm_newcat" and current_user.FAisADM:
        theCat = Cat(registre="")
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist)

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
            message = [3, "Le numero de registre existe deja!"]
            theCat.registre = None
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, msg=message)

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

        # generate the event
        session["pendingmessage"] = [0, "Chat {} rajoute dans le systeme".format(theCat.asText())]
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

    # check if you can access this
    if (theCat.owner_id != current_user.id or not current_user.FAisFA) and not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data")
        return redirect(url_for('index'))

    # handle generation of the page
    if cmd == "fa_viewcat":
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist)

    # cat commands
    if cmd == "fa_modcat" or cmd == "fa_modcatr":
        # return jsonify(request.form.to_dict())

        # update cat information
        theCat.name = request.form["c_name"]
        theCat.sex=request.form["c_sex"]
        try:
            theCat.birthdate = datetime.strptime(request.form["c_birthdate"], "%d/%m/%y")
        except ValueError:
            theCat.birthdate = None
        theCat.color=request.form["c_color"]
        theCat.longhair=request.form["c_hlen"]
        theCat.identif=request.form["c_identif"]
        theCat.description=request.form["c_description"]
        theCat.adoptable=(request.form["c_adoptable"] == "1")

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

            theVisit = VetInfo(cat_id=theCat.id, doneby_id=current_user.id, vet_id=vetId, vtype=VisitType, vdate=VisitDate,
                planned=VisitPlanned, comments=request.form["visit_comments"])
            db.session.add(theVisit)

            # if not planned, add it as event
            if not VisitPlanned:
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite veterinaire {} effectuee le {} chez {}".format(current_user.FAname, VisitType, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)

        # iterate through all the planned visits and see if they have been updated....
        # extract all planned visits which are now executed
        modvisits = []
        for k in request.form.keys():
            if k.startswith("oldv_") and k.endswith("_state") and int(request.form[k]) == 0:
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

            # modify the visit with the new data (we'll need to get all of it....)
            # if all reasons have been removed, erase it
            VisitType = vetMapToString(request.form, prefix)

            if VisitType == "--------":
                # all reasons removed, erase this
                db.session.delete(theVisit)

            else:
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

        current_user.FAlastop = datetime.now()
        db.session.commit()
        message = [0, "Informations mises a jour"]

        # if we stay on the page, regenerate it directly
        if cmd == "fa_modcatr":
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, msg=message)

        session["pendingmessage"] = message
        return redirect(url_for('index'))

    if cmd == "fa_adopted" and current_user.FAisFA:
        FAspecialAD=User.query.filter_by(FAisAD=True).first()
        theCat.owner_id = FAspecialAD.id
        # generate the event
        session["pendingmessage"] = [0, "Chat {} transfere dans les adoptes".format(theCat.asText())]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: donne aux adoptants".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('index'))

    if cmd == "fa_dead" and current_user.FAisFA:
        FAspecialDCD=User.query.filter_by(FAisDCD=True).first()
        theCat.owner_id = FAspecialDCD.id
        # generate the event
        session["pendingmessage"] = [0, "Chat {} transfere dans les decedes".format(theCat.asText())]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: indique decede".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('index'))

    if cmd == "adm_putcat" and current_user.FAisADM:
        # cat information is not updated
        FAid = int(request.form["FAid"])
        # validate the id
        theFA = User.query.filter_by(id=FAid).first()

        if theFA and FAid != theCat.owner_id:
            # generate the event
            session["pendingmessage"] = [0, "Chat {} transfere chez {}".format(theCat.asText(), theFA.FAname)]
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transfere de {} a {}".format(current_user.FAname, theCat.owner.FAname, theFA.FAname))
            db.session.add(theEvent)
            # modify the FA
            theCat.owner_id = FAid
            current_user.FAlastop = datetime.now()
            db.session.commit()

        return redirect(url_for('index'))

    # admin cat commands
    # display info about a cat
    return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist)


@app.route("/vet", methods=["POST"])
@login_required
def vetpage():
    cmd = request.form["action"]

    if cmd == "fa_vetreg":
        # query all vetinfo which was doneby the current user
        theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==current_user.id, VetInfo.planned==False)).order_by(VetInfo.vdate).all()

        return render_template("regsoins_page.html", user=current_user, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    if cmd == "fa_vetplan":
        session["otherMode"] = "special-vetplan"
        return redirect(url_for('index'))

    return redirect(url_for('index'))


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

    if cmd == "sv_globalTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats
        session["otherFA"] = "special-all"
        return redirect(url_for('index'))

    if cmd == "sv_adoptTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats with adoptable=true
        session["otherFA"] = "special-adopt"
        return redirect(url_for('index'))

    # default is return to index
    return redirect(url_for('index'))


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
    # store last access

    return redirect(url_for('index'))

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
