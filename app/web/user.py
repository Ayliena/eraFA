from app import app, db, devel_site
from app.permissions import FIRST_PRIV, NUM_PRIVS, UT_FA, UT_MANAGER, UT_REFUGE, UT_AD, UT_DCD, UT_RS, UT_HIST, UT_FATEMP, UT_VETO, TabUserTypes, TabPrivs
from app.models import Cat, User
from app.helpers import getReferentUsers
from flask import render_template, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import string
import secrets


# extract the checkbox information and set the correct flags

def defineUserPrivileges(user, form):
    for p in range(FIRST_PRIV, NUM_PRIVS):
        user.setPrivilege(p, "u_has"+TabPrivs[p] in form)

    user.defineMenus()


# filter a user list by permission, this cannot be done with a select and must be done manually
def filterUsers(users, pn):
    nu = []

    for u in users:
        if u.hasPrivilege(pn):
            nu.append(u)

    return nu


# check the user data and make sure everything is ok
# in particular: some account types are unique, so any attempt to create a new one will result in a UT_MANAGER
# at this time, only one user can have CMMOD, so any double will fail

def checkUserData(user):
    m = []

    # check unique user types
    if user.usertype in [UT_REFUGE, UT_AD, UT_DCD, UT_RS, UT_HIST, UT_FATEMP]:
        eu = User.query.filter_by(usertype=user.usertype).all()

        if len(eu) > 1 or (len(eu) == 1 and eu[0].id != user.id):
            m.append([3, "Usertype : {} est forcement unique et deja associe a {} -> type transforme en Manager".format(TabUserTypes[user.usertype], eu[0].username)])
            user.usertype = UT_MANAGER

    return m


@app.route("/user", methods=["GET", "POST"])
@login_required
def userpage():
    if not current_user.hasUsers():
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access user data")

    if request.method == "GET" or (request.method == "POST" and request.form["action"] == "adm_listusers") and current_user.hasUsers():
        # normal users
        FAlist=User.query.order_by(User.FAid).all()

        # handle any message
        if "pendingmessage" in session:
            message = session["pendingmessage"]
            session.pop("pendingmessage")
        else:
            message = []

        return render_template("user_page.html", devsite=devel_site, user=current_user, falist=FAlist, msg=message)

    # user operations
    cmd = request.form["action"]

    # prepare the table of the RFs
    RFlist = getReferentUsers()

    RFtab = {}
    for rf in RFlist:
        RFtab[rf.id] = rf.FAname

    if cmd == "adm_newuser":
        # generate an empty page to create a new user
        theFA = User()
        return render_template("user_page.html", devsite=devel_site, user=current_user, fauser=theFA, rftab=RFtab, TabUserTypes=TabUserTypes)

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

        ut = int(request.form["u_type"])
        if ut < 0 or ut > UT_VETO:
            ut = UT_FA

        # TODO: sanity check on compatible/incompatible privileges
        theFA = User(username=uname, password_hash="nologin", usertype=ut, PrivStr="0", FAname=request.form["u_iname"], FAid=request.form["u_pname"],
                     FAemail=request.form["u_email"], numcats=0)

        # sanity check
        FAresp_id = int(request.form["u_resp"]) if "u_resp" in request.form else 0

        if not FAresp_id:
            refFA = User.query.filter_by(id=FAresp_id).first()
            if not refFA or not refFA.hasReferent():
                FAresp_id = 0

        # id=0 means no resp, so set the field to NULL
        if FAresp_id == 0:
            FAresp_id = None

        theFA.FAresp_id = FAresp_id

        # set privileges
        defineUserPrivileges(theFA, request.form)
        msg = checkUserData(theFA)

        db.session.add(theFA)
        db.session.commit()

        msg.append([0, "Nouveau utilisateur '{}' creé sans mot de passe".format(theFA.username)])
        session["pendingmessage"] = msg
        return redirect(url_for('userpage'))

    if cmd == "adm_expusers":
        # export a table of all users
        FAlist=User.query.order_by(User.FAid).all()

        datfile = []

        for FA in FAlist:
            FAtype = "SPEC"
            if FA.typeVeterinaire():
                FAtype = "VET"
            if FA.typeFA():
                FAtype = "FA"

            datline = [ FA.username, FAtype, FA.FAid, FA.FAname, FA.FAemail, str(FA.numcats),
                        FA.FAlastop.strftime("%d/%m/%Y %H:%M") if FA.FAlastop else "never" ]

            datfile.append(";".join(datline))

        return Response(
            "\n".join(datfile),
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=faweb-users.dat"})

    # edit existing user
    theFA = User.query.filter_by(id=request.form["FAid"]).first()

    if not theFA:
        return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="invalid used id")

    if cmd == "adm_edituser":
        return render_template("user_page.html", devsite=devel_site, user=current_user, fauser=theFA, rftab=RFtab, TabUserTypes=TabUserTypes)

    if cmd == "adm_moduser":
        theFA.FAid = request.form["u_pname"]
        theFA.FAname = request.form["u_iname"]
        theFA.FAemail = request.form["u_email"]

        ut = int(request.form["u_type"])
        if ut < 0 or ut > UT_VETO:
            ut = UT_FA
        theFA.usertype = ut

        # sanity check
        FAresp_id = int(request.form["u_resp"]) if "u_resp" in request.form else 0

        if not FAresp_id:
            refFA = User.query.filter_by(id=FAresp_id).first()
            if not refFA or not refFA.hasReferent():
                FAresp_id = 0

        # id=0 means no resp, so set the field to NULL
        if FAresp_id == 0:
            FAresp_id = None

        theFA.FAresp_id = FAresp_id

        defineUserPrivileges(theFA, request.form)
        msg = checkUserData(theFA)

        # update the temp_owner for all the cats owned by this user, except for refuge and FAtemp
        if not theFA.typeRefuge() and not theFA.typeFAtemp():
            cats = Cat.query.filter_by(owner_id=theFA.id).all()

            for c in cats:
                c.temp_owner = theFA.FAname

        db.session.commit()
        msg.append([0, "Utilisateur {} : informations mises à jour".format(theFA.username)])
        session["pendingmessage"] = msg
        return redirect(url_for('userpage'))

    if cmd == "adm_pwduser":
        # note: CANNOT be done for adm users, this must be done manually, unless it's yourself
        if theFA.id != current_user.id and theFA.hasAdmin():
            session["pendingmessage"] = [ [2, "Impossible de modifier le MDP d'un autre Admin"] ]
            return redirect(url_for('userpage'))

        # generate a new random password
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for i in range(8))

        theFA.password_hash = generate_password_hash(password)
        db.session.commit()

        session["pendingmessage"] = [ [0, "Nouveau mot de passe pour {} : {}".format(theFA.username, password) ] ]
        return redirect(url_for('userpage'))

    # default is indicate error
    return render_template("error_page.html", user=current_user, errormessage="command error (/user)")
