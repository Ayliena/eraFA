from app import app, db, devel_site
from app.staticdata import FAidSpecial, FAC_FROZEN, FAC_UNPAID, FAC_PAID, FAC_RECONC
from app.models import Facture, User
from flask import render_template, request, redirect, url_for, jsonify, session, Response
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
                # see if we can associate to a clinic
                theClinicId = None
                theClinic = User.query.filter_by(FAid=val[1]).first()
                if theClinic:
                    theClinicId = theClinic.id

                theFact = Facture(fdate=facdate, clinic=val[1], clinic_id=theClinicId, facnumber=val[2], total=val[3], duplicata=dupnum, state=FAC_UNPAID)
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
                if theFact.state == FAC_RECONC:
                    # attempt to re-reconcile, indicate possible problem (duplicate?)
                    rv[datline] = "WARN: already reconciled: " + theFact.rdate.strftime("%Y-%m-%d")

                elif theFact.state == FAC_PAID:
                    # all is normal
                    theFact.state = FAC_RECONC
                    theFact.rdate = bankdate
                    rv[datline] = "success"

                elif theFact.state == FAC_UNPAID:
                    # should have been marked paid....
                    theFact.state = FAC_RECONC
                    theFact.pdate = bankdate
                    theFact.rdate = bankdate
                    rv[datline] = "WARN: success, but force-marked paid: " + bankdate.strftime("%Y-%m-%d")

                else: # FROZEN
                    # no choice but to indicate done....
                    theFact.state = FAC_RECONC
                    theFact.pdate = bankdate
                    theFact.rdate = bankdate
                    rv[datline] = "ERROR: paid+reconciled on FROZEN " + bankdate.strftime("%Y-%m-%d")

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
        rv[datline] = "{};{};{};{};{};{};{}".format(f.fdate.strftime("%Y-%m-%d"), f.clinic, f.facnumber, f.total, \
            f.state, f.pdate.strftime("%Y-%m-%d") if f.state>=FAC_PAID else "", f.rdate.strftime("%Y-%m-%d") if f.state>=FAC_RECONC else "")

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

    if cmd == "fact_paid" and current_user.PrivCOMPTAMOD:
        # find the facture
        theFact = Facture.query.filter_by(id=request.form["factid"]).first()
        if theFact == None:
            return render_template("error_page.html", user=current_user, errormessage="invalid fact id", FAids=FAidSpecial)

        if theFact.state == FAC_FROZEN:
            message.append( [3, "Facture <a href=\"#fac{}\">{}/{}</a> EN ATTENTE".format(theFact.id, theFact.clinic, theFact.facnumber) ] )

        elif theFact.state == FAC_PAID:
            message.append( [2, "Facture <a href=\"#fac{}\">{}/{}</a> DEJA indiquée payée".format(theFact.id, theFact.clinic, theFact.facnumber) ] )

        elif theFact.state == FAC_RECONC:
            message.append( [3, "Facture <a href=\"#fac{}\">{}/{}</a> DEJA dans un extrait banquaire".format(theFact.id, theFact.clinic, theFact.facnumber) ] )

        else:
            # indicate as paid
            theFact.state = FAC_PAID
            theFact.pdate = datetime.now()
            db.session.commit()
            message.append( [0, "Facture <a href=\"#fac{}\">{}/{}</a> indiquée payée".format(theFact.id, theFact.clinic, theFact.facnumber) ] )

    elif cmd == "fact_unpaid" and current_user.PrivCOMPTAMOD:
        # find the facture
        theFact = Facture.query.filter_by(id=request.form["factid"]).first()
        if theFact == None:
            return render_template("error_page.html", user=current_user, errormessage="invalid fact id", FAids=FAidSpecial)

        if theFact.state == FAC_RECONC:
            # you cannot indicate this unpaid!
            message.append( [3, "Facture <a href=\"#fac{}\">{}/{}</a>: reglement deja indiqué sur le relevé bancaire!".format(theFact.id, theFact.clinic, theFact.facnumber) ] )
        else:
            theFact.state = FAC_UNPAID
            db.session.commit()
            message.append( [2, "Facture <a href=\"#fac{}\">{}/{}</a> indiquée NON payée".format(theFact.id, theFact.clinic, theFact.facnumber) ] )

    elif cmd == "fact_freeze" and current_user.PrivCOMPTAMOD:
        # find the facture
        theFact = Facture.query.filter_by(id=request.form["factid"]).first()
        if theFact == None:
            return render_template("error_page.html", user=current_user, errormessage="invalid fact id", FAids=FAidSpecial)

        if theFact.state >= FAC_PAID:
            # you cannot indicate this unpaid!
            message.append( [3, "Facture <a href=\"#fac{}\">{}/{}</a> DEJA indiquée payée!".format(theFact.id, theFact.clinic, theFact.facnumber) ] )
        elif theFact.state == FAC_UNPAID:
            # freeze this
            theFact.state = FAC_FROZEN
            db.session.commit()
            message.append( [2, "Facture <a href=\"#fac{}\">{}/{}</a> mise en attente".format(theFact.id, theFact.clinic, theFact.facnumber) ] )

    elif cmd == "fact_unfreeze" and current_user.PrivCOMPTAMOD:
        # find the facture
        theFact = Facture.query.filter_by(id=request.form["factid"]).first()
        if theFact == None:
            return render_template("error_page.html", user=current_user, errormessage="invalid fact id", FAids=FAidSpecial)

        if theFact.state != FAC_FROZEN:
            # uh?
            message.append( [3, "Facture <a href=\"#fac{}\">{}/{}</a>: n'est pas en attente!".format(theFact.id, theFact.clinic, theFact.facnumber) ] )
        else:
            # ufreeze this
            theFact.state = FAC_UNPAID
            db.session.commit()
            message.append( [2, "Facture <a href=\"#fac{}\">{}/{}</a> règlement désormais possible".format(theFact.id, theFact.clinic, theFact.facnumber) ] )

    elif cmd == "fact_filter":
        # update the filter

        # store the options in the session data
        showUnpaid = ("opt_unpaid" in request.form)
        showPaid = ("opt_paid" in request.form)
        showReconciled = ("opt_reconciled" in request.form)
        filtClinic = request.form["opt_clinic"] if "opt_clinic" in request.form else ""
        filtDates = [request.form[did] for did in ["d_comp0", "d_comp1", "d_reg0", "d_reg1"]]

        # save for the future
        session["optCOMPTA"] = ("1;" if showUnpaid else "0;")+("1;" if showPaid else "0;")+("1;" if showReconciled else "0;")+filtClinic+";"+";".join(filtDates)

    elif cmd == "fact_export":
        # will process at the end
        pass

    elif cmd != "":
      return render_template("error_page.html", user=current_user, errormessage="invalid command", FAids=FAidSpecial)

    # get the options from the session data (if available), otherwise use defaults
    if "optCOMPTA" in session:
        opt = session["optCOMPTA"].split(";")
        showUnpaid = (opt[0] == '1')
        showPaid = (opt[1] == '1')
        showReconciled = (opt[2] == '1')
        filtClinic = opt[3]
        filtDates = opt[4:]
    else:
        showUnpaid = True
        showPaid = True
        showReconciled = False
        filtClinic = ""
        filtDates = ["","","",""]

    fquery = Facture.query

    if current_user.PrivCOMPTASELF:
        fquery = fquery.filter(Facture.clinic_id==current_user.id)

    # make sure we keep the ones requested (note: frozen == unpaid)
    # no idea on how to do this in a better way....
    if showUnpaid:
        if showPaid:
            if showReconciled:
                pass
            else:
                fquery = fquery.filter(Facture.state<FAC_RECONC)
        else:
            if showReconciled:
                fquery = fquery.filter(Facture.state!=FAC_PAID)
            else:
                fquery = fquery.filter(Facture.state<FAC_PAID)
    else:
        if showPaid:
            if showReconciled:
                fquery = fquery.filter(Facture.state>FAC_UNPAID)
            else:
                fquery = fquery.filter(Facture.state==FAC_PAID)
        else:
            if showReconciled:
                fquery = fquery.filter(Facture.state>FAC_PAID)
            else:
                fquery = None

    if fquery:
        # add filtering by clinic
        if filtClinic:
            fquery = fquery.filter(Facture.clinic.contains(filtClinic))

        # add filtering by date (dates are stored as dd/mm/yy, so we need to convert)
        for i in range(0,4):
            if filtDates[i]:
                try:
                    dv = datetime.strptime(filtDates[i], "%Y-%m-%d")
                except ValueError:
                    dv = None

                if dv:
                    if i == 0:
                        fquery = fquery.filter(Facture.fdate>=dv)
                    elif i == 1:
                        fquery = fquery.filter(Facture.fdate<=dv)
                    elif i == 2:
                        fquery = fquery.filter(Facture.pdate>=dv)
                    elif i == 3:
                        fquery = fquery.filter(Facture.pdate<=dv)

        # order by date
        facs = fquery.order_by(Facture.fdate).all()
    else:
        facs = []

    # calculate the totals
    # values are: unpaid, paid, grand total
    ftotal = [Decimal(0), Decimal(0), Decimal(0)]
    for f in facs:
        if f.state < FAC_PAID:  # unpaid
            ftotal[0] = ftotal[0] + f.total
        if f.state > FAC_UNPAID: # paid, reconciled or not
            ftotal[1] = ftotal[1] + f.total
        ftotal[2] = ftotal[2] + f.total

    if cmd == "fact_export":
        # generate the CSV instead of the page
        datfile = []
        datfile.append("Date,Clinique,N.Facture,Total TTC,Réglée le,Rapprochée le")

        for f in facs:
            datline = [ f.fdate.strftime("%Y-%m-%d"), '"'+f.clinic+'"', '"'+f.facnumber+'"',str(f.total),("" if f.state<FAC_PAID else f.pdate.strftime('%Y-%m-%d')),("" if f.state<FAC_RECONC else f.rdate.strftime('%Y-%m-%d')) ]
            datfile.append(",".join(datline))

        return Response(
            "\n".join(datfile),
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=facturesERA.csv"})

    return render_template("factures_page.html", devsite=devel_site, user=current_user, msg=message, FAids=FAidSpecial, cumulative=ftotal, factures=facs, facfilter=[showUnpaid, showPaid, showReconciled, filtClinic]+filtDates)
