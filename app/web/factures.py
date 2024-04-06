from app import app, db, devel_site
from app.staticdata import FAidSpecial
from app.models import Facture
from flask import render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import and_
from decimal import Decimal
#import json

@app.route('/facupload', methods=["POST"])
def factures_upload():
    # the data is received as a json dictionary
    jsondata = request.json
    apikey = jsondata.get("apikey", "nil")

    if apikey != app.config['APIKEY']:
        rv = {
            "code": -1,
            "message": "unauthorized"
        }
        return jsonify(rv)

    rv = { "code": 1, "message": "data processed" }

    # get all the lines
    i = 0
    while True:
        datline = "data{}".format(i)
        i = i + 1
        line = jsondata.get(datline, "")
        if len(line) == 0:
            break

        val = line.split(';')

        try:
            facdate = datetime.strptime(val[0], "%Y-%m-%d")
        except ValueError:
            rv[datline] = "invalid date"
            continue

        # add the data, if it doesn't already exist
        theFact = Facture.query.filter(and_(Facture.clinic==val[1],Facture.facnumber==val[2])).first()
        if theFact != None:
            # already exists, this should not happen
            rv[datline] = "duplicate entry"
            # do absolutely nothing
            continue
        else:
            theFact = Facture(fdate=facdate, clinic=val[1], facnumber=val[2], total=val[3], paid=False)
            db.session.add(theFact)
            rv[datline] = "success"

    db.session.commit()
    return jsonify(rv)


@app.route('/factures', methods=["GET", "POST"])
@login_required
def factures_page():
    if not current_user.PrivCOMPTA:
        return redirect(url_for('fapage'))

    if request.method == "POST":
        cmd = request.form["action"]
    else:
        cmd = ""

    message = []

    if cmd == "fact_paid":
        # find the facture
        theFact = Facture.query.filter_by(id=request.form["factid"]).first()
        if theFact == None:
            return render_template("error_page.html", user=current_user, errormessage="invalid fact id", FAids=FAidSpecial)

        theFact.paid = True
        theFact.pdate = datetime.now()
        db.session.commit()
        message.append( [0, "Facture {}/{} indiquée payée".format(theFact.clinic, theFact.facnumber) ] )

    elif cmd == "fact_unpaid":
        # find the facture
        theFact = Facture.query.filter_by(id=request.form["factid"]).first()
        if theFact == None:
            return render_template("error_page.html", user=current_user, errormessage="invalid fact id", FAids=FAidSpecial)

        theFact.paid = False
        db.session.commit()
        message.append( [2, "Facture {}/{} indiquée NON payée".format(theFact.clinic, theFact.facnumber) ] )

    elif cmd != "":
        return render_template("error_page.html", user=current_user, errormessage="invalid command", FAids=FAidSpecial)

    # regenerate the list
    facs = Facture.query.order_by(Facture.fdate).all()
    # cumulate the total
    ftotal = Decimal(0)
    for f in facs:
        if not f.paid:
            ftotal = ftotal + f.total

    return render_template("factures_page.html", devsite=devel_site, user=current_user, msg=message, FAids=FAidSpecial, cumulative=ftotal, factures=facs)
