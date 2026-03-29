from app import app, db, devel_site
from app.staticdata import FAC_FROZEN, FAC_UNPAID, FAC_PAID, FAC_RECONC, FAC_BEINGPAID
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


@app.route('/api/factures/<int:id>/set-state', methods=['POST'])
@login_required
def factures_pay(id):
    # check if we can
    if not current_user.hasComptaMod():
        return jsonify({'error': "missing privilege"}), 401

    # get the data
    fac = Facture.query.get(id)

    if not fac:
        return jsonify({'error': 'invalid fac_id'}), 404

    # see what we must do
    new_state = request.get_json()['state']

    # consistency check on state transitions
    if new_state == "frz":
        if fac.state != FAC_UNPAID:
            return jsonify({'error': 'Impossible de mettre en attente'}), 405

        # everything seems to be ok, update the information
        fac.state = FAC_FROZEN
        db.session.commit()

    elif new_state == "ufz":
        if fac.state != FAC_FROZEN:
            return jsonify({'error': 'La facture n\'est pas en attente'}), 405

        # everything seems to be ok, update the information
        fac.state = FAC_UNPAID
        db.session.commit()

    elif new_state == "reg":
        # make sure noone-else is working on it
        if fac.beingpaidby_id:
            return jsonify({'error': "Deja en reglement par {}".format(fac.beingpaidby.FAname)}), 409

        if fac.state != FAC_UNPAID:
            return jsonify({'error': "Impossible de mettre en reglement"}), 405

        # everything seems to be ok, update the information
        fac.state = FAC_BEINGPAID
        fac.beingpaidby_id = current_user.id
        db.session.commit()

    elif new_state == "rno":
        if fac.state != FAC_BEINGPAID:
            return jsonify({'error': "Impossible d'interrompre le reglement d'une facture qui n'etait pas en reglement"}), 405

        # everything seems to be ok, update the information
        fac.state = FAC_UNPAID
        fac.beingpaidby_id = None
        db.session.commit()

    elif new_state == "rok":
        if fac.state != FAC_BEINGPAID:
            return jsonify({'error': "Impossible d'indiquer reglee une facture qui n'etait pas en reglement"}), 405

        # everything seems to be ok, update the information
        fac.state = FAC_PAID
        fac.beingpaidby_id = None
        fac.pdate = datetime.now()
        db.session.commit()

    elif new_state == "cnc":
        if fac.state != FAC_PAID:
            return jsonify({'error': "Impossible d'annuler le reglement"}), 405

        # everything seems to be ok, update the information
        fac.state = FAC_UNPAID
        db.session.commit()

    # this will be executed for all new_state, which includes the 'rfr' (refresh)
    # update (or not...) the state
    return render_template("_fac_st_bt.html", user=current_user, fac=fac)


@app.route('/factures', methods=["GET", "POST"])
def factures_page():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    if not (current_user.hasComptaSelf() or current_user.hasCompta()):
        return redirect(url_for('fapage'))

    if request.method == "POST":
        cmd = request.form["action"]
    else:
        cmd = ""

    message = []

    if cmd == "fact_filter":
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
      return render_template("error_page.html", user=current_user, errormessage="invalid command")

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

    if current_user.hasComptaSelf():
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
        if f.state == FAC_PAID or f.state == FAC_RECONC:  # paid
            ftotal[1] = ftotal[1] + f.total
        else: # unpaid
            ftotal[0] = ftotal[0] + f.total
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

    return render_template("factures_page.html", devsite=devel_site, user=current_user, msg=message, cumulative=ftotal, factures=facs, facfilter=[showUnpaid, showPaid, showReconciled, filtClinic]+filtDates)
