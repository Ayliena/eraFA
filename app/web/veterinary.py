from app import app, db
from app.staticdata import TabColor, TabSex, TabHair, FAidSpecial
from app.models import User, Cat, VetInfo, Event
from app.helpers import vetMapToString, vetAddStrings, ERAsum
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import and_
from datetime import datetime


@app.route("/vet", methods=["GET", "POST"])
@login_required
def vetpage():
    if request.method == "GET":
        return redirect(url_for('fapage'))

    cmd = request.form["action"]

    # this is a workaround to allow the 1st menu to return to the main view using a single form
    if cmd == "fa_catlist":
        # just return to the default main page
        session["otherMode"] = None
        return redirect(url_for('fapage'))

    if cmd == "fa_vetreg":
        # query all vetinfo which was doneby the FA
        FAid = current_user.id
        if "otherFA" in session:
            FAid = session["otherFA"]
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if not faexists:
                return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

            if theFA.FAresp_id != current_user.id and not (current_user.FAisOV or current_user.FAisADM):
                FAid = current_user.id

        theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==False)).order_by(VetInfo.vdate).all()

        if FAid != current_user.id:
            return render_template("regsoins_page.html", user=current_user, otheruser=theFA, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

        return render_template("regsoins_page.html", user=current_user, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    if cmd == "fa_vetplan":
        session["otherMode"] = "special-vetplan"
        return redirect(url_for('fapage'))

    if cmd == "fa_vetmv" or cmd == "fa_vetmvd":
        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): invalid vetinfo id", FAids=FAidSpecial)

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if not (theCat.owner_id == current_user.id and current_user.FAisFA) and not (theCat.owner.FAresp_id == current_user.id) and not current_user.FAisADM:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): insufficient privileges", FAids=FAidSpecial)

                # convert the visit to "effectuee" and log the event
                theCat.vetshort = vetAddStrings(theCat.vetshort, theVisit.vtype)
                theVisit.planned = False

                if cmd == "fa_vetmvd":
                    try:
                        theVisit.vdate = datetime.strptime(request.form["c_vdate"], "%d/%m/%y")
                    except ValueError:
                        theVisit.vdate = datetime.now()

                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} effectuée le {} chez {}".format(current_user.FAname, theVisit.vtype, theVisit.vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)
                db.session.commit()

        # return to the same page
        return redirect(url_for('fapage'))

    if cmd == "fa_vetmpl":
        FAid = current_user.id
        if "otherFA" in session:
            FAid = session["otherFA"]
            theFA = User.query.filter_by(id=FAid).first()
            faexists = theFA is not None;

            if not faexists:
                return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

            # permissions: ADM and OV see all
            # RF can see the ones they manage + adopt/dead/refuge
            if not (current_user.FAisRF and theFA.FAresp_id != current_user.id) and not (current_user.FAisRF and (FAid == FAidSpecial[0] or
                        FAid == FAidSpecial[1] or FAid == FAidSpecial[3])) and not (current_user.FAisOV or current_user.FAisADM):
                FAid = current_user.id

        VETlist = User.query.filter_by(FAisVET=True).all()

        if FAid != current_user.id:
            return render_template("vet_page.html", user=current_user, otheruser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                cats=Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all(), FAids=FAidSpecial, VETids=VETlist)

        return render_template("vet_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
            cats=Cat.query.filter_by(owner_id=current_user.id).order_by(Cat.regnum).all(), FAids=FAidSpecial, VETids=VETlist)


    if cmd == "fa_vetmpl_save":
        # vet list will be needed
        VETlist = User.query.filter_by(FAisVET=True).all()

        # start by decoding the visit data
        # generate the vetinfo record, if any, and the associated event
        VisitType = vetMapToString(request.form, "visit")

        if VisitType != "--------":
            # validate the vet
            vet = next((x for x in VETlist if x.id==int(request.form["visit_vet"])), None)

            if not vet:
                return render_template("error_page.html", user=current_user, errormessage="vet id is invalid", FAids=FAidSpecial)
            else:
                vetId = vet.id

            try:
                VisitDate = datetime.strptime(request.form["visit_date"], "%d/%m/%y")
            except ValueError:
                VisitDate = datetime.now()

            VisitPlanned = (int(request.form["visit_state"]) == 1)

            # if executed, then cumulate with the global
            if not VisitPlanned:
                et = "effectuee le"
            else:
                et = "planifiee pour le"
        else:
            session["pendingmessage"] = [ [ 2, "Aucun soin indique" ] ]
            return redirect(url_for('fapage'))

        # now iterate on all cats and add the visit
        catregs = []

        for key in request.form.keys():
            if key[0:3] == 're_':
                catid = int(key[3:])

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=catid).first()

                if not theCat:
                    return render_template("error_page.html", user=current_user, errormessage="fa_vetmpl_save: invalid cat id {}".format(catid), FAids=FAidSpecial)

                if not (theCat.owner_id == current_user.id and current_user.FAisFA) and not (theCat.owner.FAresp_id == current_user.id) and not current_user.FAisADM:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): insufficient privileges", FAids=FAidSpecial)

                catregs.append(theCat.regStr())

                # generate the visit and the event
                # we always associate the visit to the current owner
                theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vetId, vtype=VisitType, vdate=VisitDate,
                    planned=VisitPlanned, comments=request.form["visit_comments"])
                db.session.add(theVisit)
                db.session.commit()  # needed for vet.FAname

                # add it as event (planned or not)
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, VisitType, et, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)
                db.session.commit()

        if not catregs:
            session["pendingmessage"] = [ [ 2, "Aucun chat selectionne" ] ]
        else:
            session["pendingmessage"] = [ [ 0, "Visite {} enregistree pour les chats: {}".format(VisitType, ", ".join(catregs)) ] ]

        # return to vet page
        return redirect(url_for('fapage'))

    if cmd == "fa_vetbon":
        # generate the data for the bon
        catlist = []
        catregs = []
        theFA = None
        # vaccinations, rappels, sterilisations, castrations, identifications, tests fiv/felv, soins
        # if vtype is "soins" then we append the comment as visit description
        vtypes = [0, 0, 0, 0, 0, 0, 0]
        vdate = None
        comments = []
        # the QR code contains: ERA;<who authorized>;<today's date>;<FAid>;<visit date>;<cat regs>;<vtypes joined as string>;<check>
        # check is a 12-byte string obtained by md5sum of previous part + some random junk + base64_encode + cut in half

        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): invalid vetinfo id", FAids=FAidSpecial)

                if not vdate:
                    vdate = theVisit.vdate

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if not (theCat.owner_id == current_user.id and current_user.FAisFA) and not (theCat.owner.FAresp_id == current_user.id) and not current_user.FAisADM:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): insufficient privileges", FAids=FAidSpecial)

                if not theFA:
                    theFA = theCat.owner

                # cumulate the information
                catlist.append(theCat)
                catregs.append(theCat.regStr())

                if theVisit.vtype[0] != '-':
                    vtypes[0] += 1
                if theVisit.vtype[1] != '-':
                    vtypes[1] += 1
                if theVisit.vtype[2] != '-':
                    vtypes[1] += 1
                if theVisit.vtype[3] != '-':
                    if theCat.sex == 2:
                        vtypes[3] += 1
                    else:
                        vtypes[2] += 1
                if theVisit.vtype[4] != '-':
                    vtypes[4] += 1
                if theVisit.vtype[5] != '-':
                    vtypes[5] += 1
                if theVisit.vtype[6] != '-':
                    comments.append(theVisit.comments)
                    vtypes[6] += 1
                if theVisit.vtype[7] != '-':
                    vtypes[1] += 1

        # if nothing was selected, stay here
        if not catlist:
            session["pendingmessage"] = [ [ 2, "Aucune visite selectionnee" ] ]
            return redirect(url_for('fapage'))

        bdate = datetime.today()

        # generate the qrcode string
        qrstr = "ERA;{};{};{};{};{};{};".format(current_user.FAid, bdate.strftime('%Y%m%d'), theFA.FAid, vdate.strftime('%Y%m%d'), "/".join(catregs), "".join(str(e) for e in vtypes))
        qrstr = qrstr + ERAsum(qrstr)

        return render_template("bonveto_page.html", user=current_user, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, cats=catlist, fa=theFA, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    if cmd == "adm_vbver":
        bvcode = request.form["vb_qrcode"]

        if not bvcode:
            session["pendingmessage"] = [ [ 2, "Aucune code a verifier" ] ]
            return redirect(url_for('fapage'))

        if len(bvcode) > 15 and ERAsum(bvcode[0:-12]) == bvcode[-12:]:
            session["pendingmessage"] = [ [ 0, "Le code fourni est valable" ] ]
        else:
            session["pendingmessage"] = [ [ 3, "Le code fourni n'est PAS valable!" ] ]

        return redirect(url_for('fapage'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/vet)", FAids=FAidSpecial)
