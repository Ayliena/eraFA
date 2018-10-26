
# ERA FA management flask app

# jsonify is for debugging
from flask import Flask, render_template, redirect, request, url_for,jsonify
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
TabColor = ["INCONNU", "BEIGE", "BEIGE ET BLANC", "BLANC", "BLUE POINT", "CREME", "ECAILLE DE TORTUE", "GRIS", "GRIS CHARTREUX", "GRIS ET BLANC",
             "NOIR", "NOIR ET BLANC", "NOIR ET SMOKE", "NOIR PLASTRON BLANC", "ROUX", "ROUX ET BLANC", "SEAL POINT", "TABBY BLANC", "TABBY BRUN", "TABBY GRIS",
             "TIGRE", "TIGRE BEIGE", "TIGRE BRUN", "TIGRE CREME", "TIGRE GRIS", "TRICOLORE"]
TabSex = ["INCONNU", "FEMELLE", "MALE"]
TabHair = ["COURT", "MI-LONG", "LONG"]
# static since it changes rarely, NOTE: it must also be changed in cat_page.html
VETlist = [ [8, "Veto (commentaires)"], [ 6, "AMCB Veterinaires" ], [7, "Clinique Mont. Verte"]  ]

# special FA ids (static)
FAidAD = 3
FAidDCD = 5

# --------------- HELPER FUNCTIONS

def vetMapToString(vetmap):
    str = "-------";
    if vetmap["visit_pv"]:
        str[0] = 'V'
    if vetmap["visit_r1"]:
        str[1] = '1'
    if vetmap["visit_r2"]:
        str[2] = '2'
    if vetmap["visit_sc"]:
        str[3] = 'S'
    if vetmap["visit_id"]:
        str[4] = 'P'
    if vetmap["visit_tf"]:
        str[5] = 'T'
    if vetmap["visit_gen"]:
        str[6] = 'X'
    if vetmap["visit_rr"]:
        str[7] = 'R'
    return str

def vetStringToMap(vetstr):
    vmap = {}
    vmap["visit_pv"] = (str[0] == 'V')
    vmap["visit_r1"] = (str[1] == '1')
    vmap["visit_r2"] = (str[2] == '2')
    vmap["visit_sc"] = (str[3] == 'S')
    vmap["visit_id"] = (str[4] == 'P')
    vmap["visit_tf"] = (str[5] == 'T')
    vmap["visit_gen"] = (str[6] == 'X')
    vmap["visit_rr"] = (str[7] == 'R')
    return vmap

def vetAddStrings(vetstr1, vetstr2):
    str = vetstr1;
    for i in range(0,7):
        if str[i] == '-':
            str[i] = vetstr2[i];

    return str

# --------------- USER CLASS

# to create a new user:
# > flask shell
# > from flask_app import db, User
# > from werkzeug.security import generate_password_hash
# newuser = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False)
# newuserFA = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False)
# newuserVET = User(username="login", password_hash=generate_password_hash("password"), FAname="VET name(long)", FAid="name(short)", FAemail="invalid@invalid", FAisFA=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=True)
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
    FAisDCD = db.Column(db.Boolean, nullable=False)
    FAisVET = db.Column(db.Boolean, nullable=False)
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

class Cat(db.Model):

    __tablename__ = "cats"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('User', foreign_keys=owner_id)
    nextowner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    nextowner = db.relationship('User', foreign_keys=nextowner_id)
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


# --------------- VETINFO CLASS

class VetInfo(db.Model):

    __tablename__ = "vetinfo"

    id = db.Column(db.Integer, primary_key=True)
    cat_id = db.Column(db.Integer, db.ForeignKey('cats.id'), nullable=False)
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


# --------------- WEB PAGES

@app.route('/', methods=["GET", "POST"])
@app.route('/index', methods=["GET", "POST"])
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    # generate the page
    if request.method == "GET":
        return render_template("main_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
            cats=Cat.query.filter( and_(Cat.owner_id==current_user.id, Cat.nextowner_id== None) ).all(),
            ocats=Cat.query.filter( and_(Cat.owner_id==current_user.id, Cat.nextowner_id != None) ).all(),
            icats=Cat.query.filter_by(nextowner_id=current_user.id).all())
#            cats=current_user.cats, icats=current_user.icats)

    # handle commands
    cmd = request.form["action"]

    # alternate GET command for another FA
    if cmd == "sv_fastate" and (current_user.FAisOV or current_user.FAisADM):
        FAid = int(request.form["FAid"]);
        # validate the id
        theFA = User.query.filter_by(id=FAid).first()
        faexists = theFA is not None;

        if faexists:
            # check for special FAs
            if theFA.FAisAD or theFA.FAisDCD:
                return render_template("main_spc_page.html", user=current_user, otheruser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    cats=Cat.query.filter( and_(Cat.owner_id==FAid, Cat.nextowner_id== None) ).all())

            return render_template("main_page.html", user=current_user, otheruser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                cats=Cat.query.filter( and_(Cat.owner_id==FAid, Cat.nextowner_id== None) ).all(),
                ocats=Cat.query.filter( and_(Cat.owner_id==FAid, Cat.nextowner_id != None) ).all(),
                icats=Cat.query.filter_by(nextowner_id=FAid).all())

        # if the fa doesn't exist, return to index
        return render_template("error_page.html", user=current_user, errormessage="attempt to view invalid FA")
        return redirect(url_for('index'))

    # get the cat
    theCat = Cat.query.filter_by(id=request.form["catid"]).first()
    if theCat == None:
        return render_template("error_page.html", user=current_user, errormessage="invalid cat id")
        return redirect(url_for('index'))

    # check if you can access this
    if theCat.owner_id != current_user.id and theCat.nextowner_id != current_user.id and not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data")
        return redirect(url_for('index'))

    # handle accept/cancel transfert
    if cmd == "fa_accepttr" and current_user.FAisFA and current_user.id == theCat.nextowner_id:
        # generate the event
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="recu chez {} de {}".format(current_user.FAname, theCat.nextowner.FAname))
        db.session.add(theEvent)
        # transfer here
        theCat.owner_id = theCat.nextowner_id
        theCat.nextowner_id = None
        db.session.commit()

        return redirect(url_for('index'))

    if cmd == "fa_canceltr" and current_user.FAisFA and current_user.id == theCat.owner_id:
        # generate the event
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="transfert de {} a {} annulle".format(current_user.FAname, theCat.nextowner.FAname))
        db.session.add(theEvent)
        # cancel the transfer
        theCat.nextowner_id = None
        db.session.commit()

        return redirect(url_for('index'))

    if cmd == "adm_deletecat" and current_user.FAisADM:
        # erase the cat and all the associated information from the database
        # NOTE THAT THIS IS IRREVERSIBLE AND LEAVES NO TRACE
        Event.query.filter_by(cat_id=theCat.id).delete()
        VetInfo.query.filter_by(cat_id=theCat.id).delete()
        db.session.delete(theCat)
        db.session.commit()

    return redirect(url_for('index'))


@app.route("/cat", methods=["POST"])
def catpage():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    cmd = request.form["action"]

    if cmd == "fa_return":
        return redirect(url_for('index'))

    # prepare the list of FAs for transfers
    FAlist=User.query.filter_by(FAisFA=True).all()

    # generate an empty page to add a new cat
    if cmd == "adm_newcat" and current_user.FAisADM:
        theCat = Cat(registre="")
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist)

    if (cmd == "adm_addcathere" or cmd == "adm_addcatgiveFA" or cmd == "adm_addcatputFA") and current_user.FAisADM:
        # generate the new cat using the form information
        vetstr = vetMapToString(request.form)

        theCat = Cat(registre=request.form["c_registre"], name=request.form["c_name"], sex=request.form["c_sex"],
                    color=request.form["c_color"], longhair=request.form["c_hlen"], identif=request.form["c_identif"],
                    description=request.form["c_description"], vetshort=vetstr, adoptable=(request.form["c_adoptable"]=="1"))

        # if for any reason the FA is invalid, then put it here
        if cmd != "adm_addcathere":
            FAid = int(request.form["FAid"]);
            # validate the id
            faexists = db.session.query(User.id).filter_by(id=FAid).scalar() is not None;

            if cmd == "adm_addcatgiveFA" and faexists:
                theCat.owner_id = current_user.id
                theCat.nextowner_id = FAid
            elif cmd == "adm_addcatputFA" and faexists:
                theCat.owner_id = FAid
            else:
                theCat.owner_id = current_user.id

        else: # cmd == "addcathere"
            theCat.owner_id = current_user.id

        # generate the event
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="rajoute dans le systeme par {}".format(current_user.FAname))
        db.session.add(theEvent)

        db.session.add(theCat)
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
        theCat.color=request.form["c_color"]
        theCat.longhair=request.form["c_hlen"]
        theCat.identif=request.form["c_identif"]
        theCat.description=request.form["c_description"]
        theCat.adoptable=(request.form["c_adoptable"] == "1")

        # generate the vetinfo record, if any, and the associated event
        newvisit =  ("visit_pv" in request.form or "visit_r1" in request.form or "visit_r2" in request.form or
            "visit_sc" in request.form or "visit_id" in request.form or "visit_tf" in request.form or "visit_gen" in  request.form)

        if newvisit:
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

            VisitType = ""

            theVisit = VetInfo(cat_id=theCat.id, doneby_id=current_user.id, vet_id=vetId, vtype=VisitType, vdate=VisitDate,
                planned=(request.form["visit_state"] == 1), comments=request.form["visit_comments"])
            db.session.add(theVisit)

        # TODO
#        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="rajoute dans le systeme")
#        db.session.add(theEvent)

        db.session.commit()

        # if we stay on the page, regenerate it directly
        if cmd == "fa_modcatr":
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist)

        return redirect(url_for('index'))

    if cmd == "fa_givecat" and current_user.FAisFA:
        # cat information is not updated
        FAid = int(request.form["FAid"]);
        # validate the id
        faexists = db.session.query(User.id).filter_by(id=FAid).scalar() is not None;

        if faexists and FAid != theCat.owner_id:
            theCat.nextowner_id = FAid
            # generate the event
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="donne par {} a {}".format(current_user.FAname, theCat.nextowner.FAname))
            db.session.add(theEvent)
            db.session.commit()

        return redirect(url_for('index'))

    if cmd == "fa_adopted" and current_user.FAisFA:
        FAspecialAD=User.query.filter_by(FAisAD=True).first()
        theCat.owner_id = FAspecialAD.id
        # generate the event
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="donne aux adoptants par {}".format(current_user.FAname))
        db.session.add(theEvent)
        db.session.commit()
        return redirect(url_for('index'))

    if cmd == "fa_dead" and current_user.FAisFA:
        FAspecialDCD=User.query.filter_by(FAisDCD=True).first()
        theCat.owner_id = FAspecialDCD.id
        # generate the event
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="indique decede par {}".format(current_user.FAname))
        db.session.add(theEvent)
        db.session.commit()
        return redirect(url_for('index'))

    if cmd == "adm_putcat" and current_user.FAisADM:
        # cat information is not updated
        FAid = int(request.form["FAid"])
        # validate the id
        faexists = db.session.query(User.id).filter_by(id=FAid).scalar() is not None

        if faexists and FAid != theCat.owner_id:
            theCat.owner_id = FAid
            theCat.nextowner_id = None
            # generate the event
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="transfere par {} a {}".format(current_user.FAname, theCat.owner.FAname))
            db.session.add(theEvent)
            db.session.commit()

        return redirect(url_for('index'))

    if cmd == "fa_addvet" and current_user.FAisFA:
        # add vet information
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=[])

    # admin cat commands
    # display info about a cat
    return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist)


@app.route("/list", methods=["POST"])
def listpage():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    cmd = request.form["action"]

    if cmd == "sv_viewFA" and (current_user.FAisADM or current_user.FAisOV):
        # normal FAs
        FAlist=User.query.filter_by(FAisFA=True).all()
        # special FAs
        if current_user.FAisADM:
            FAspecialAD=User.query.filter_by(FAisAD=True).first()
            FAspecialDCD=User.query.filter_by(FAisDCD=True).first()

        return render_template("list_page.html", user=current_user, falist=FAlist, faad=FAspecialAD, fadcd=FAspecialDCD)

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
    user.FAlastop = datetime.now()
    db.session.commit()

    return redirect(url_for('index'))

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
