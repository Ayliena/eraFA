from app import app, db, devel_site
from app.staticdata import FAidSpecial
from app.models import User
from flask import render_template, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import string
import secrets


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

        return render_template("user_page.html", devsite=devel_site, user=current_user, falist=FAlist, rftab=RFtab, FAids=FAidSpecial, msg=message)

    # user operations
    cmd = request.form["action"]

    if cmd == "adm_newuser":
        # generate an empty page to create a new user
        theFA = User()
        return render_template("user_page.html", devsite=devel_site, user=current_user, fauser=theFA, rftab=RFtab, FAids=FAidSpecial)

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

    if cmd == "adm_expusers":
        # export a table of all users
        FAlist=User.query.order_by(User.FAid).all()

        datfile = []

        for FA in FAlist:
            FAtype = "SPEC"
            if FA.FAisVET:
                FAtype = "VET"
            if FA.FAisFA:
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
        return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="invalid used id", FAids=FAidSpecial)

    if cmd == "adm_edituser":
        return render_template("user_page.html", devsite=devel_site, user=current_user, fauser=theFA, rftab=RFtab, FAids=FAidSpecial)

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
