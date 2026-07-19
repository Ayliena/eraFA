from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair, NO_VISIT, NO_VET, GEN_VET, DEFAULT_VET
from app.models import User, Cat
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from datetime import datetime

@app.route("/refuge", methods=["POST"])
@login_required
def refugepage():
    # handle actions executed by refuge_page
    if not current_user.typeRefuge() and not current_user.hasRefuge():
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges")
    
    cmd = request.form["action"]

    if cmd == "ref_cancel":
        # return to default display
        session["otherMode"] = None
        return redirect(url_for('fapage'))

    if cmd == "ref_doreorg":
        updated = False

        msg = "Cage mise à jour:"

        # iterate on all cage definitions and update the modified ones
        for k in request.form.keys():

            if k.startswith("cg_"):
                catid = int(k[3:])
                
                # find the cat
                theCat = Cat.query.filter_by(id=catid).first()
                # this should not happen, but let's not crash everything if it does
                if not theCat:
                    continue

                # update the cage if modified
                if theCat.temp_owner != request.form[k]:
                    msg = msg + " " + theCat.regStr()
                    theCat.temp_owner = request.form[k]
                    updated = True

        if updated:
            db.session.commit()

        session["pendingmessage"] = [ [0, msg] ]

        # return to default view
        session["otherMode"] = None
        return redirect(url_for('fapage'))

    # this should never be reached
    return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="command error (/refuge)")
    
