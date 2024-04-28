from app import app, db, devel_site
from app.staticdata import FAidSpecial
from app.models import Facture
from flask import render_template, request, redirect, url_for, jsonify, session
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import and_, or_
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

    # see if it's new factures or it's a list of bank payments
    cmd = jsondata.get("command", "none")

    if cmd == "newfact":
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

            # decode the duplicata number
            dupnum = 0
            if val[4].startswith("Duplicata"):
                dupnum = int(val[4][9])

            # add the data, if it doesn't already exist
            theFact = Facture.query.filter(and_(Facture.clinic==val[1],Facture.facnumber==val[2])).first()
            if theFact:
                # already exists, update duplicata if needed
                if dupnum > theFact.duplicata:
                    theFact.duplicata = dupnum
                    rv[datline] = "updated duplicata"
                else:
                    rv[datline] = "existing entry"

                continue
            else:
                theFact = Facture(fdate=facdate, clinic=val[1], facnumber=val[2], total=val[3], duplicata=dupnum, paid=False, reconciled=False)
                db.session.add(theFact)
                rv[datline] = "success"

        db.session.commit()

    elif cmd == "bankreport":
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
                bankdate = datetime.strptime(val[0], "%Y-%m-%d")
            except ValueError:
                rv[datline] = "invalid date"
                continue

            theFact = Facture.query.filter(and_(Facture.clinic==val[1],Facture.facnumber==val[2])).first()

            if theFact:
                if not theFact.reconciled:
                    # mark as reconciled
                    theFact.reconciled = True
                    theFact.rdate = bankdate
                    rv[datline] = "success"
                else:
                    rv[datline] = "already reconciled"

            else:
                rv[datline] = "facture not found"

        db.session.commit()

    else:
        rv = { "code": -2, "message": "invalid command" }

    return jsonify(rv)


@app.route('/facdownload', methods=["POST"])
def factures_download():
    # the data is received as a json dictionary
    jsondata = request.json
    apikey = jsondata.get("apikey", "nil")

    if apikey != app.config['APIKEY']:
        rv = {
            "code": -1,
            "message": "unauthorized"
        }
        return jsonify(rv)

    try:
        datefrom = datetime.strptime(jsondata.get("date_from", "2000-01-01"), "%Y-%m-%d")
    except ValueError:
        rv["code"] = -1
        rv["message"] = "invalid from date"
        return jsonify(rv)

    try:
        dateto = datetime.strptime(jsondata.get("date_to", "2099-12-31"), "%Y-%m-%d")
    except ValueError:
        rv["code"] = -2
        rv["message"] = "invalid to date"
        return jsonify(rv)

    # sanity check
    # TODO: compare dates and switch if inverted

    rv = { "code": 1, "message": "query processed" }

    theFacts = Facture.query.filter(and_(Facture.fdate>=datefrom, Facture.fdate<=dateto)).order_by(Facture.fdate).all()

    i = 0
    for f in theFacts:
        datline = "data{}".format(i)
        i = i + 1
        rv[datline] = "{};{};{};{};{};{};{};{}".format(f.fdate.strftime("%Y-%m-%d"), f.clinic, f.facnumber, f.total, f.paid, f.pdate.strftime("%Y-%m-%d") if f.paid else "", f.reconciled, f.rdate.strftime("%Y-%m-%d") if f.reconciled else "")

    # return the result
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

        if theFact.paid:
            message.append( [2, "Facture {}/{} DEJA indiquée payée".format(theFact.clinic, theFact.facnumber) ] )

        elif theFact.reconciled:
            message.append( [3, "Facture {}/{} DEJA dans un extrait banquaire".format(theFact.clinic, theFact.facnumber) ] )

        else:
            # indicate as paid
            theFact.paid = True
            theFact.pdate = datetime.now()
            db.session.commit()
            message.append( [0, "Facture {}/{} indiquée payée".format(theFact.clinic, theFact.facnumber) ] )

    elif cmd == "fact_unpaid":
        # find the facture
        theFact = Facture.query.filter_by(id=request.form["factid"]).first()
        if theFact == None:
            return render_template("error_page.html", user=current_user, errormessage="invalid fact id", FAids=FAidSpecial)

        if theFact.reconciled:
            # you cannot indicate this unpaid!
            message.append( [3, "Facture {}/{}: reglement deja indiqué sur le relevé banquaire!".format(theFact.clinic, theFact.facnumber) ] )
        else:
            theFact.paid = False
            db.session.commit()
            message.append( [2, "Facture {}/{} indiquée NON payée".format(theFact.clinic, theFact.facnumber) ] )

    elif cmd == "fact_filter":
        # update the filter

        # store the options in the session data
        showUnpaid = ("opt_unpaid" in request.form)
        showPaid = ("opt_paid" in request.form)
        showReconciled = ("opt_reconciled" in request.form)

        # save for the future
        session["optCOMPTA"] = ("1" if showUnpaid else "0")+("1" if showPaid else "0")+("1" if showReconciled else "0")

    elif cmd != "":
      return render_template("error_page.html", user=current_user, errormessage="invalid command", FAids=FAidSpecial)

    # get the options from the session data (if available), otherwise use defaults
    if "optCOMPTA" in session:
        opt = session["optCOMPTA"]
        showUnpaid = (opt[0] == '1')
        showPaid = (opt[1] == '1')
        showReconciled = (opt[2] == '1')
    else:
        showUnpaid = True
        showPaid = True
        showReconciled = False

    # I have no idea how to do this cleanly with a query....
    if showUnpaid:
        if showPaid:
            if showReconciled:
                facs = Facture.query.order_by(Facture.fdate).all()
            else:
                facs = Facture.query.filter(Facture.reconciled==False).order_by(Facture.fdate).all()
        else:
            if showReconciled:
                facs = Facture.query.filter(Facture.paid==False).order_by(Facture.fdate).all()
            else:
                facs = Facture.query.filter(and_(Facture.reconciled==False,Facture.paid==False)).order_by(Facture.fdate).all()
    else:
        if showPaid:
            if showReconciled:
                facs = Facture.query.filter(or_(Facture.reconciled==True,Facture.paid==True)).order_by(Facture.fdate).all()
            else:
                facs = Facture.query.filter(and_(Facture.reconciled==False,Facture.paid==True)).order_by(Facture.fdate).all()
        else:
            if showReconciled:
                facs = Facture.query.filter(and_(Facture.reconciled==True,Facture.paid==False)).order_by(Facture.fdate).all()
            else:
                facs = []

    # cumulate the total
    ftotal = Decimal(0)
    for f in facs:
        if not f.paid and not f.reconciled:
            ftotal = ftotal + f.total

    return render_template("factures_page.html", devsite=devel_site, user=current_user, msg=message, FAids=FAidSpecial, cumulative=ftotal, factures=facs, facfilter=[showUnpaid, showPaid, showReconciled])
