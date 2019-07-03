from app import app, db
from app.staticdata import FAidSpecial
from app.models import  Cat
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user


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


@app.route("/help")
@login_required
def helppage():
    return render_template("help_page.html", user=current_user, FAids=FAidSpecial)
