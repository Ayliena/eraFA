from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair, FAidSpecial, ACC_NONE, ACC_RO, ACC_MOD, ACC_FULL, ACC_TOTAL
from app.models import User, Cat, VetInfo, Event
from app.helpers import vetMapToString, vetAddStrings, ERAsum, encodeRegnum, accessPrivileges, getViewUser, isFATemp, isRefuge
from flask import render_template, redirect, request, url_for, session, Markup
from flask_login import login_required, current_user
from sqlalchemy import and_
from datetime import datetime
from html import escape


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

    # these two handle the main page for a vet clinic, swapping between current and history
    if cmd == "vet_vilist" and current_user.FAisVET:
        session["otherMode"] = None
        return redirect(url_for('fapage'))

    if cmd == "vet_vihist" and current_user.FAisVET:
        session["otherMode"] = "special-vethistory"
        return redirect(url_for('fapage'))

    # action = plan/indicate multiple visits
    if cmd == "fa_vetplan":
        session["otherMode"] = "special-vetplan"
        return redirect(url_for('fapage'))

    # define the owner of the cats we're working on
    FAid, theFA = getViewUser()

    if not FAid:
        return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

    # determine what we can do
    catMode, vetMode, searchMode = accessPrivileges(theFA)

    if cmd == "fa_vetreg" and catMode > ACC_NONE:
        # query all vetinfo which was doneby the FA
        theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==False)).order_by(VetInfo.vdate).all()

        return render_template("regsoins_page.html", user=current_user, viewuser=theFA, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    # action = visit done / done at specified date
    if vetMode >= ACC_MOD and (cmd == "fa_vetmv" or cmd == "fa_vetmvd"):
        # this is just to see if anything was done
        visits_selected = 0

        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats or one of your visits)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): invalid vetinfo id", FAids=FAidSpecial)

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()

                # for vet, limit access to visits planned to self
                if current_user.FAisVET and theVisit.vet_id != current_user.id:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): insufficient privileges", FAids=FAidSpecial)

                # convert the visit to "effectuee" and log the event
                theCat.vetshort = vetAddStrings(theCat.vetshort, theVisit.vtype)
                theVisit.planned = False

                if cmd == "fa_vetmvd":
                    try:
                        theVisit.vdate = datetime.strptime(request.form["c_vdate"], "%d/%m/%y")
                    except ValueError:
                        theVisit.vdate = datetime.now()

                visits_selected += 1
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} effectuée le {} chez {}".format(current_user.FAname, theVisit.vtype, theVisit.vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)
                db.session.commit()

        # if nothing was selected, indicate it
        if not visits_selected:
            session["pendingmessage"] = [ [ 2, "Aucune visite selectionnee" ] ]

        # return to the same page
        return redirect(url_for('fapage'))

    # action = delete visit
    if vetMode >= ACC_MOD and cmd == "fa_vetmdel":
        # iterate on the checkboxes to see which cats are to be processed
        catregs = []

        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetareq: invalid vetinfo id", FAids=FAidSpecial)

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if theCat.owner_id != FAid and vetMode < ACC_FULL:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetareq: insufficient privileges", FAids=FAidSpecial)

                # you can access this, delete the visit
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} annullée".format(current_user.FAname, theVisit.vtype))
                db.session.add(theEvent)
                db.session.delete(theVisit)
                catregs.append(theCat.regStr())

        db.session.commit()

        session["pendingmessage"] = [ [ 0, "Visites annullees pour les chats: {}".format(", ".join(catregs)) ] ]

        return redirect(url_for('fapage'))

    # plan multiple visits (generate page)
    if vetMode >= ACC_MOD and cmd == "fa_vetmpl":
        VETlist = User.query.filter_by(FAisVET=True).all()

        if FAid == FAidSpecial[4]:
            theCats = Cat.query.filter_by(owner_id=FAid).order_by(Cat.temp_owner,Cat.regnum).all()
        else:
            theCats = Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all()

        return render_template("vet_page.html", devsite=devel_site, user=current_user, viewuser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
            cats=theCats, FAids=FAidSpecial, VETids=VETlist)

    # plan multiple visits (execute action)
    if vetMode >= ACC_MOD and cmd == "fa_vetmpl_save":
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

                if theCat.owner_id != FAid and vetMode < ACC_FULL:
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

    # action = request authorization
    if vetMode >= ACC_MOD and cmd == "fa_vetareq":
        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetareq: invalid vetinfo id", FAids=FAidSpecial)

               # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if theCat.owner_id != FAid and vetMode < ACC_FULL:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetareq: insufficient privileges", FAids=FAidSpecial)

                # you can access this, indicate that the visit is now requested
                theVisit.requested = True

        db.session.commit()
        return redirect(url_for('fapage'))

    # action = grant authorization or transfer to the vet
    if vetMode >= ACC_FULL and (cmd == "fa_vetauth" or cmd == "fa_vettrans"):
        # iterate on the checkboxes to see which cats are to be processed
        # session["pendingmessage"] = [[1, "Resultats" ]]

        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetauth: invalid vetinfo id", FAids=FAidSpecial)

               # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if theCat.owner_id != FAid:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetauth: insufficient privileges", FAids=FAidSpecial)

                # authorization is useless for FA_temp, but is ok in the case of transfer to vet
                if isFATemp(theCat.owner_id) and cmd == "fa_vetauth":
                    session["pendingmessage"] = [ [ 3, "Authoriser une visite pour une FA temporaire est inutile".format(theCat.regStr()) ] ]
                    return redirect(url_for('fapage'))

                # you can access this, indicate that the visit is now authorized (even if the authorization was not requested)
                theVisit.requested = False
                theVisit.validby_id = current_user.id
                theVisit.validdate = datetime.now()

                # indicate as transferred if it's what was asked
                theVisit.transferred = True if cmd == "fa_vettrans" else False

        db.session.commit()

        return redirect(url_for('fapage'))

    # action = revoke authorizaion
    if vetMode >= ACC_FULL and cmd == "fa_vetadel":
        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetadel: invalid vetinfo id", FAids=FAidSpecial)

               # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if theCat.owner_id != FAid:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetadel: insufficient privileges", FAids=FAidSpecial)

                # you can access this, indicate that the visit is now authorized (even if the authorization was not requested)
                theVisit.transferred = False
                theVisit.validby_id = None
                theVisit.validdate = None

        db.session.commit()
        return redirect(url_for('fapage'))

    # action = generate bonVeto
    if vetMode >= ACC_MOD and cmd == "fa_vetbon":
        # generate the data for the bon
        catlist = []
        catregs = []
        catvtypes = []
        FAname = None
        FAid = None
        theAuthFA = None
        VETname = None

        # vaccinations, rappels, sterilisations, castrations, identifications, tests fiv/felv, soins
        # if vtype is "soins" then we append the comment as visit description
        vtypes = [0, 0, 0, 0, 0, 0, 0]
        vdate = None
        comments = []
        # the QR code contains: ERA;<today's date>;<who authorized>;<authorization date>;<FAid>;<visit date>;<cat regs>;<vtypes joined as string>;<check>
        # check is a 12-byte string obtained by md5sum of previous part + some random junk + base64_encode + cut in half

        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (for a FA = must be one of your cats, for a VET = visit must be in your clinic
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetbon: invalid vetinfo id", FAids=FAidSpecial)

                if not vdate:
                    vdate = theVisit.vdate

                # validate the access and the authorization depending if FA or VET
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                canAccess = False
                isAuthorized = False

                if (current_user.FAisVET):
                    # a VET can generate the bonVeto if the visit is transferred to its clinic
                    canAccess = (theVisit.vet_id == current_user.id)
                    isAuthorized = theVisit.transferred
                else:
                    canAccess = (theCat.owner_id == theFA.id)
                    isAuthorized = theVisit.validby_id or vetMode >= ACC_FULL

                if not canAccess:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetbon: insufficient privileges", FAids=FAidSpecial)

                # do we need authorization?
                if not isAuthorized:
                    session["pendingmessage"] = [ [ 3, "La visite du chat {} n'est pas autorisee!".format(theCat.regStr()) ] ]
                    return redirect(url_for('fapage'))

                # generate the FAname/FAid and fail if multiples are defined
                baseFAid = FAid

                if isFATemp(theCat.owner_id):
                    # for temp_fa, use the name associated to the cat
                    FAname = theCat.temp_owner
                    FAid = "[{}]".format(FAname)
                elif isRefuge(theCat.owner_id):
                    # if the FA is refuge, define FAid for the QR code, but not FAname
                    FAid = theCat.owner.FAid
                    FAname = ''
                else:
                    # default: define id and name of the FA
                    FAname = theVisit.doneby.FAname
                    FAid = theVisit.doneby_id

                if baseFAid:
                    if baseFAid != FAid:
                        session["pendingmessage"] = [ [ 3, "Impossible de generer un seul bon pour des visites de plusieurs FA!" ] ]
                        return redirect(url_for('fapage'))

                # manage validation source and date
                if not theAuthFA:
                    if vetMode >= ACC_FULL:
                        theAuthFA = current_user
                        authdate = datetime.now()
                    elif theVisit.validby_id:
                        theAuthFA = theVisit.validby
                        authdate = theVisit.validdate

                # note the vet name (we just use the 1st)
                if not VETname:
                    VETname = theVisit.vet.FAname

                # cumulate the information
                catlist.append(theCat)
                catregs.append(theCat.regStr())
                catvtypes.append(theVisit.vtype)

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

        # check the auth
        if not theAuthFA:
            # this is a major problem which should not happen
            return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetbon: no authorization FA found??", FAids=FAidSpecial)

        bdate = datetime.today()

        # indicate that we did this
        for theCat,vtype in zip(catlist, catvtypes):
            # add it as event (planned or not)
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: bon imprime pour {} le {} chez {} ({})".format(current_user.FAname, vtype, vdate.strftime("%d/%m/%y"), VETname, FAname))
            db.session.add(theEvent)

        db.session.commit()

        # generate the qrcode string
        qrstr = "ERA;{};{};{};{};{};{};".format(bdate.strftime('%Y%m%d'), theAuthFA.FAid, authdate.strftime('%Y%m%d'), FAid, vdate.strftime('%Y%m%d'), "/".join(catregs), "".join(str(e) for e in vtypes))
        qrstr = qrstr + ERAsum(qrstr)

        return render_template("bonveto_page.html", user=current_user, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, authFA=theAuthFA.FAname, cats=catlist, faname=FAname, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    # action = generate bonVeto WITHOUT planned visit (from search page, usually)
    if vetMode == ACC_TOTAL and cmd == "fa_vetbonfast":
        # generate the data for the bon
        # note that no planned visit is generated, so apart from the PDF, no information is stored anywhere
        catlist = []
        catregs = []
        catvtypes = []

        # the name used will be the one of the first FA (unless overridden)
        FAname = None

        # the count will just be the number of cats (but we keep it split, just in case...)
        vtypes = [0, 0, 0, 0, 0, 0, 0]
        comments = []
        # the QR code contains: ERA;<today's date>;<who authorized>;<authorization date>;<FAid>;<visit date>;<cat regs>;<vtypes joined as string>;<check>
        # check is a 12-byte string obtained by md5sum of previous part + some random junk + base64_encode + cut in half

        try:
            vdate = datetime.strptime(request.form["visit_date"], "%d/%m/%y")
        except ValueError:
            vdate = datetime.now()

        # manage validation source and date
        theAuthFA = current_user
        authdate = datetime.now()

        # generate the vetinfo from the form
        VisitType = vetMapToString(request.form, "visit")

        # in this special case, we assume that "filled comments -> X type", so we force it
        if request.form["visit_comments"]:
            VisitType = VisitType[:6] + "X" + VisitType[7:]

        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                catid = int(key[3:])

                # find the cat
                theCat = Cat.query.filter_by(id=catid).first()

                if not FAname:
                    if theCat.owner_id == FAidSpecial[4]:
                        FAname = theCat.temp_owner
                        FAid = "[{}]".format(FAname)
                    elif theCat.owner_id == FAidSpecial[0] or theCat.owner_id == FAidSpecial[2]:
                        FAname = None
                        FAid = "[{}]".format(theCat.owner_id)
                    else:
                        FAname = theCat.owner.FAname
                        FAid = theCat.owner.FAid

                # cumulate the information
                catlist.append(theCat)
                catregs.append(theCat.regStr())
                catvtypes.append(VisitType)

                if VisitType[0] != '-':
                    vtypes[0] += 1
                if VisitType[1] != '-':
                    vtypes[1] += 1
                if VisitType[2] != '-':
                    vtypes[1] += 1
                if VisitType[3] != '-':
                    if theCat.sex == 2:
                        vtypes[3] += 1
                    else:
                        vtypes[2] += 1
                if VisitType[4] != '-':
                    vtypes[4] += 1
                if VisitType[5] != '-':
                    vtypes[5] += 1
                if VisitType[6] != '-':
                    if not comments:
                        # we also fix the comments so that newlines are respected
                        comments.append(Markup(escape(request.form["visit_comments"]).replace("\n","<br>")))
                    vtypes[6] += 1
                if VisitType[7] != '-':
                    vtypes[1] += 1

            # if nothing was selected, return an error and stay here
            if not catlist:
                session["pendingmessage"] = [ [ 2, "Aucun chat selectionne" ] ]
                return redirect(url_for('fapage'))

            # if no visit type was selected... same
            if sum(vtypes) == 0:
                session["pendingmessage"] = [ [ 2, "Aucune visite selectionnee" ] ]
                return redirect(url_for('fapage'))

        # if requested, override the generated FA name
        if request.form["visit_faname"]:
            FAname = request.form["visit_faname"]
            FAid = "[{}]".format(FAname)

        # since visit is unplanned, this is also used as visit date
        bdate = datetime.today()

        # indicate that we did this
        for theCat,vtype in zip(catlist, catvtypes):
            # add it as event (planned or not)
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: bon imprime pour {} le {} ({})".format(current_user.FAname, vtype, bdate.strftime("%d/%m/%y"), FAname))
            db.session.add(theEvent)

        db.session.commit()

        # generate the qrcode string
        qrstr = "ERA;{};{};{};{};{};{};".format(bdate.strftime('%Y%m%d'), theAuthFA.FAid, authdate.strftime('%Y%m%d'), FAid, vdate.strftime('%Y%m%d'), "/".join(catregs), "".join(str(e) for e in vtypes))
        qrstr = qrstr + ERAsum(qrstr)

        return render_template("bonveto_page.html", user=current_user, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, authFA=theAuthFA.FAname, cats=catlist, faname=FAname, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    # action = generate bonVeto for unregistered cats
    if vetMode == ACC_TOTAL and cmd == "fa_vetbonunreg":
        # generate the data for the bon using the provided info
        catlist = []
        catregs = []

        # if the name is empty, no field will appear in the bon
        FAname = request.form["visit_faname"]

        # the count will just be the number of cats (but we keep it split, just in case...)
        vtypes = [0, 0, 0, 0, 0, 0, 0]
        comments = []
        # the QR code contains: ERA;<today's date>;<who authorized>;<authorization date>;<FAname>;<visit date>;<cat regs>;<vtypes joined as string>;<check>
        # check is a 12-byte string obtained by md5sum of previous part + some random junk + base64_encode + cut in half

        try:
            vdate = datetime.strptime(request.form["visit_date"], "%d/%m/%y")
        except ValueError:
            vdate = datetime.now()

        # manage validation source and date
        theAuthFA = current_user
        authdate = datetime.now()

        # increment the number of the cat
        # TODO: get from db state table
        regnum = (authdate.year - 2000) * 10000 + 3000;

        # generate the vetinfo from the form
        VisitType = vetMapToString(request.form, "visit")

        # in this special case, we assume that "filled comments -> X type", so we force it
        if request.form["visit_comments"]:
            VisitType = VisitType[:6] + "X" + VisitType[7:]

        # iterate on the table to see how many cats to add

        for key in ("c1", "c2", "c3", "c4", "c5"):
            kage = key + "_age";
            age = int(request.form[kage])
            if age:
                # cat is defined, add the data
                urcat = {'regnum' : encodeRegnum(regnum) }
                catregs.append(encodeRegnum(regnum))
                regnum = regnum + 1

                ksex = key + "_sex"
                kcol = key + "_color"

                if age == 1:
                    urcat['age'] = "chaton"
                elif age == 2:
                    urcat['age'] = "chat"
                elif age == 3:
                    urcat['age'] = "chat age"

                if int(request.form[ksex]):
                    urcat['sex'] = TabSex[int(request.form[ksex])]

                if int(request.form[kcol]):
                    urcat['col'] = TabColor[int(request.form[kcol])]

                # forget about the name for now
                # urcat['name'] = ....

                # cumulate the information
                catlist.append(urcat)

                if VisitType[0] != '-':
                    vtypes[0] += 1
                if VisitType[1] != '-':
                    vtypes[1] += 1
                if VisitType[2] != '-':
                    vtypes[1] += 1
                if VisitType[3] != '-':
                    if int(request.form[ksex]) == 2:
                        vtypes[3] += 1
                    else:
                        vtypes[2] += 1
                if VisitType[4] != '-':
                    vtypes[4] += 1
                if VisitType[5] != '-':
                    vtypes[5] += 1
                if VisitType[6] != '-':
                    if not comments:
                        # we also fix the comments so that newlines are respected
                        comments.append(Markup(escape(request.form["visit_comments"]).replace("\n","<br>")))
                    vtypes[6] += 1
                if VisitType[7] != '-':
                    vtypes[1] += 1

            # if nothing was selected, return an error and stay here
            if not catlist:
                session["pendingmessage"] = [ [ 2, "Aucun chat selectionne" ] ]
                return redirect(url_for('unregpage'))

            # if no visit type was selected... same
            if sum(vtypes) == 0:
                session["pendingmessage"] = [ [ 2, "Aucune visite selectionnee" ] ]
                return redirect(url_for('unregpage'))

        bdate = datetime.today()

        # generate the qrcode string
        qrstr = "ERA;{};{};{};{};{};{};".format(bdate.strftime('%Y%m%d'), theAuthFA.FAid, authdate.strftime('%Y%m%d'), FAname, vdate.strftime('%Y%m%d'), "/".join(catregs), "".join(str(e) for e in vtypes))
        qrstr = qrstr + ERAsum(qrstr)

        return render_template("bonveto_page.html", user=current_user, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, authFA=theAuthFA.FAname, ucats=catlist, faname=FAname, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    # action = validate QR code
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
