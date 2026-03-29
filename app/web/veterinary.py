from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair, NO_VISIT, NO_VET, GEN_VET, DEFAULT_VET
from app.permissions import UT_VETO
from app.models import User, Cat, VetInfo, Event
from app.helpers import ERAsum, encodeRegnum, getViewUser, canAccessCat, canAccessCats, ACC_NONE, ACC_RO, ACC_MOD
from app.vetvisits import vetMapToString, vetAddStrings, vetIsPrimo, vetIsRappel1, vetIsRappelAnn, vetIsIdent, vetIsTest, vetIsSteril, \
    vetIsSoins, vetIsDepara, cat_addVetVisit, cat_executeVetVisit, cat_deleteVisit
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
    if cmd == "vet_vilist" and current_user.typeVeterinaire():
        session["otherMode"] = None
        return redirect(url_for('fapage'))

    if cmd == "vet_vihist" and current_user.typeVeterinaire():
        session["otherMode"] = "special-vethistory"
        return redirect(url_for('fapage'))

    if cmd == "vet_histfilt" and current_user.typeVeterinaire():
        session["otherMode"] = "special-vethistory"  # this should not be necessary
        # update the filter
        # store the options in the session data
        filtFA = request.form["opt_fa"] if "opt_fa" in request.form else ""
        filtDates = [request.form[did] for did in ["d_visit0", "d_visit1"]]
        # save for the future
        session["optVETOHIST"] = (filtFA+";"+";".join(filtDates))
        return redirect(url_for('fapage'))

    # action = plan/indicate multiple visits
    if cmd == "fa_vetplan":
        session["otherMode"] = "special-vetplan"
        return redirect(url_for('fapage'))

    # define the owner of the cats we're working on
    FAid, theFA = getViewUser()

    if not FAid:
        return render_template("error_page.html", user=current_user, errormessage="invalid FA id")

    msgs = []

    # display registre des soins
    # - possible if you can access the cats
    if cmd == "fa_vetreg":
        if canAccessCats(theFA, current_user) != ACC_NONE:
            # query all vetinfo which was doneby the FA
            theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==False)).order_by(VetInfo.vdate).all()

            return render_template("regsoins_page.html", user=current_user, viewuser=theFA, visits=theVisits, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    # action = visit done / done at specified date
    # - possible for a vet associated to the visit or if you have MOD access to the cats
    if cmd == "fa_vetmv" or cmd == "fa_vetmvd":
        # this is just to see if anything was done
        visits_selected = 0

        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats or one of your visits)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetmv(d): invalid vetinfo id")

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()

                # for vet, limit access to visits planned to self
                if current_user.typeVeterinaire():
                    if theVisit.vet_id != current_user.id:
                        msgs.append( [2, "/vet:fa_vetmv(d): Acces non autorise au chat {}".format(theCat.asText()) ] )
                        continue

                elif canAccessCat(theCat, current_user) != ACC_MOD:
                    msgs.append( [2, "/vet:fa_vetmv(d): Acces non autorise au chat {}".format(theCat.asText()) ] )
                    continue

                VisitDate = None

                # convert the visit to "effectuee" and log the event
#                theCat.vetshort = vetAddStrings(theCat.vetshort, theVisit.vtype)
#                theVisit.planned = False

                if cmd == "fa_vetmvd":
                    VisitDate = request.form["c_vdate"]
                    if VisitDate == "":
                        VisitDate = "today"

                vres = cat_executeVetVisit(vvid, theCat, VisitDate)

                if vres:
                    if vres.startswith("visit"):
                        msgs.append( [2, vres ] )
                    else:
                        msgs.append( [0, "Informations du chat {} mises a jour: {}".format(theCat.regStr(), vres) ] )

                visits_selected += 1


        if visits_selected:
            db.session.commit()
        else:
            # if nothing was selected, indicate it
            msgs.append( [ 2, "Aucune visite modifiee" ] )

        session["pendingmessage"] = msgs

        # return to the same page
        return redirect(url_for('fapage'))

    # action = delete visit
    # - possible if you have MOD access
    if cmd == "fa_vetmdel":
        # iterate on the checkboxes to see which cats are to be processed
        catregs = []

        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetareq: invalid vetinfo id")

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if canAccessCat(theCat, current_user) != ACC_MOD:
                    msgs.append( [2, "/vet:fa_vetareq: Acces non autorise au chat {}".format(theCat.asText()) ] )
                    continue

                # you can access this, delete the visit
                cat_deleteVisit(theCat, theVisit, False)
                catregs.append(theCat.regStr())

        db.session.commit()

        session["pendingmessage"] = [ [ 0, "Visites annullees pour les chats: {}".format(", ".join(catregs)) ] ]

        return redirect(url_for('fapage'))

    # plan multiple visits (generate page)
    # - possible if you have MOD access to the cats of the user
    if cmd == "fa_vetmpl":
        if canAccessCats(theFA, current_user) == ACC_MOD:
            VETlist = User.query.filter_by(usertype=UT_VETO).all()

            if theFA.typeFAtemp():
                theCats = Cat.query.filter_by(owner_id=FAid).order_by(Cat.temp_owner,Cat.regnum).all()
            else:
                theCats = Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all()

            return render_template("vet_page.html", devsite=devel_site, user=current_user, viewuser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                cats=theCats, VETids=VETlist, VETdef=DEFAULT_VET)

    # plan multiple visits (execute action)
    # - possible with MOD access to the cats
    if cmd == "fa_vetmpl_save":
        # vet list will be needed
        VETlist = User.query.filter_by(usertype=UT_VETO).all()

        # start by decoding the visit data
        # generate the vetinfo record, if any, and the associated event
        VisitType = vetMapToString(request.form, "visit")
        VisitVet = request.form["visit_vet"]
        VisitDate = request.form["visit_date"]
        VisitPlanned = (int(request.form["visit_state"]) == 1)
        VisitComments = request.form["visit_comments"]

        if VisitType == NO_VISIT:
            session["pendingmessage"] = [ [ 2, "Aucun soin indique" ] ]
            return redirect(url_for('fapage'))

        # now iterate on all cats and add the visit
        catregs = []
        vres = ""

        for key in request.form.keys():
            if key[0:3] == 're_':
                catid = int(key[3:])

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=catid).first()

                if not theCat:
                    return render_template("error_page.html", user=current_user, errormessage="fa_vetmpl_save: invalid cat id {}".format(catid))

                if canAccessCat(theCat, current_user) != ACC_MOD:
                    msgs.append( [2, "fa_vetmpl_save: Acces non autorise au chat {}".format(theCat.asText()) ] )
                    continue

                catregs.append(theCat.regStr())

                # generate the visit and the event
                vres = vres + " " + theCat.regStr() + "{" + cat_addVetVisit(VETlist, theCat, VisitPlanned, VisitType, VisitVet, VisitDate, VisitComments) + "}"

        if not catregs:
            session["pendingmessage"] = [ [ 2, "Aucun chat modifie" ] ]
        else:
            session["pendingmessage"] = [ [ 0, "Visite {} enregistree pour les chats: {}".format(VisitType, ", ".join(catregs)) ] ]

        # return to vet page
        return redirect(url_for('fapage'))

    # action = request authorization
    # - possible for FA users on their own visits
    if cmd == "fa_vetareq":
        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetareq: invalid vetinfo id")

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()

                if not theCat:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetareq: invalid cat id {}".format(catid))

                if canAccessCat(theCat, current_user) != ACC_MOD:
                    msgs.append( [3, "/vet:fa_vetareq: Acces non autorise au chat {}".format(theCat.asText()) ] )
                    continue

                if theCat.isPrivate():
                    msgs.append( [ 3, "Les bons veto ne sont pas possibles pour les chats prives".format(theCat.regStr()) ] )
                    continue

                # you can access this, indicate that the visit is now requested
                theVisit.requested = True

        db.session.commit()
        return redirect(url_for('fapage'))

    # action = grant authorization or transfer to the vet
    # - possible if you have the BonVeto privilege
    if cmd == "fa_vetauth" or cmd == "fa_vettrans":
        # iterate on the checkboxes to see which cats are to be processed
        # session["pendingmessage"] = [[1, "Resultats" ]]

        if not current_user.hasBonVeto():
            msgs.append( [2, "/vet:fa_vetauth: Non autorise a generer des bons veto" ] )
            return redirect(url_for('fapage'))

        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetauth: invalid vetinfo id")

                # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if canAccessCat(theCat, current_user) != ACC_MOD:
                    msgs.append( [3, "/vet:fa_vetauth: Acces non autorise au chat {}".format(theCat.asText()) ] )
                    continue

                # transfer is only valid if there's a reasonable vet associated to the visit
                if cmd == "fa_vettrans" and (theVisit.vet_id == NO_VET or theVisit.vet_id == GEN_VET):
                    msgs.append([3, "Transfert impossible pour {}, clinique non definie!".format(theCat.regStr())])
                    continue

                # authorization is useless for FA_temp, but is ok in the case of transfer to vet
                if theCat.owner.typeFAtemp() and cmd == "fa_vetauth":
                    session["pendingmessage"] = [ [ 3, "Authoriser une visite pour une FA temporaire est inutile".format(theCat.regStr()) ] ]
                    return redirect(url_for('fapage'))

                # you can access this, indicate that the visit is now authorized (even if the authorization was not requested)
                theVisit.requested = False
                theVisit.validby_id = current_user.id
                theVisit.validdate = datetime.now()

                # indicate as transferred if it's what was asked
                if cmd == "fa_vettrans":
                    msgs.append([0, "Visite du {} transferee".format(theCat.regStr())])
                    theVisit.transferred = True
                else:
                    msgs.append([0, "Visite du {} autorisee".format(theCat.regStr())])
                    theVisit.transferred = False

        db.session.commit()
        session["pendingmessage"] = msgs

        return redirect(url_for('fapage'))

    # action = revoke authorizaion
    # - possible if you have the BonVeto privilege
    if cmd == "fa_vetadel":
        if not current_user.hasBonVeto():
            msgs.append( [2, "/vet:fa_vetauth: Non autorise a generer des bons veto" ] )
            return redirect(url_for('fapage'))

        # iterate on the checkboxes to see which cats are to be processed
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                # make sure you can access this (= must be one of your cats)
                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if not theVisit:
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetadel: invalid vetinfo id")

               # find the cat and make sure we can access it
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()
                if canAccessCat(theCat, current_user) != ACC_MOD:
                    msgs.append( [3, "/vet:fa_vetauth: Acces non autorise au chat {}".format(theCat.asText()) ] )
                    continue

                # you can access this, indicate that the visit is now authorized (even if the authorization was not requested)
                theVisit.transferred = False
                theVisit.validby_id = None
                theVisit.validdate = None

        db.session.commit()
        return redirect(url_for('fapage'))

    # action = generate bonVeto
    # - possible if the user has BonVeto, or the visit is authorized/transferred
    if cmd == "fa_vetbon":
        # generate the data for the bon
        catlist = []
        catregs = []
        catvtypes = []
        FAname = None
        FAid = None
        theAuthFA = None
        VETname = None

        # vaccinations, rappels, sterilisations, castrations, identifications, tests fiv/felv, soins, deparasitages
        # if vtype is "soins" then we append the comment as visit description
        vtypes = [0, 0, 0, 0, 0, 0, 0, 0]
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
                    return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetbon: invalid vetinfo id")

                if not vdate:
                    vdate = theVisit.vdate

                # validate the access and the authorization depending if FA or VET
                theCat = Cat.query.filter_by(id=theVisit.cat_id).first()

                # no bon veto for private cats
                if theCat.isPrivate():
                    session["pendingmessage"] = [ [ 3, "Les bons veto ne sont pas possibles pour les chats prives".format(theCat.regStr()) ] ]
                    return redirect(url_for('fapage'))

                isAuthorized = False

                # authorization is true for Vet accessing an owned visit which is transferred
                if current_user.typeVeterinaire():
                    if theVisit.vet_id != current_user.id:
                        return render_template("error_page.html", user=current_user, errormessage="/vet:fa_vetbon: vet mismatch")

                    isAuthorized = theVisit.transferred
                    theAuthFA = theVisit.validby

                # authorization is true if the user can access the cat and the visit is validated OR the user has BonVeto
                elif canAccessCat(theCat, current_user) != ACC_NONE:
                    if theVisit.validby_id:
                        isAuthorized = True
                        theAuthFA = theVisit.validby
                    elif current_user.hasBonVeto():
                        isAuthorized = True

                # do we need authorization?
                if not isAuthorized:
                    session["pendingmessage"] = [ [ 3, "La visite du chat {} n'est pas autorisee!".format(theCat.regStr()) ] ]
                    return redirect(url_for('fapage'))

                # generate the FAname/FAid and fail if multiples are defined
                baseFAid = FAid

                if theCat.owner.typeFAtemp():
                    # for temp_fa, use the name associated to the cat
                    FAname = theCat.temp_owner
                    FAid = "[{}]".format(FAname)
                elif theCat.owner.typeRefuge():
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

                if vetIsPrimo(theVisit.vtype):
                    vtypes[0] += 1
                if vetIsRappel1(theVisit.vtype):
                    vtypes[1] += 1
                if vetIsRappelAnn(theVisit.vtype):
                    vtypes[1] += 1
                if vetIsSteril(theVisit.vtype):
                    if theCat.sex == 2:
                        vtypes[3] += 1
                    else:
                        vtypes[2] += 1
                if vetIsIdent(theVisit.vtype):
                    vtypes[4] += 1
                if vetIsTest(theVisit.vtype):
                    vtypes[5] += 1
                if vetIsSoins(theVisit.vtype):
                    vtypes[6] += 1
                    comments.append(theVisit.comments)
                if vetIsDepara(theVisit.vtype):
                    vtypes[7] += 1

        # if nothing was selected, stay here
        if not catlist:
            session["pendingmessage"] = [ [ 2, "Aucune visite selectionnee" ] ]
            return redirect(url_for('fapage'))

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

        pdfname = "bon-veto-{}".format(FAname)
        return render_template("bonveto_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, bvtitle=pdfname, authFA=theAuthFA.FAname, cats=catlist, faname=FAname, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    # action = generate bonVeto WITHOUT planned visit (from search page, usually)
    # the used need BonVeto (and access to the cat)
    if cmd == "fa_vetbonfast":
        if not current_user.hasBonVeto():
            msgs.append( [2, "/vet:fa_vetbonfast: Non autorise a generer des bons veto" ] )
            return redirect(url_for('fapage'))

        # generate the data for the bon
        # note that no planned visit is generated, so apart from the PDF, no information is stored anywhere
        catlist = []
        catregs = []
        catvtypes = []

        # the name used will be the one of the first FA (unless overridden)
        FAname = None
        PostAdoption = 0

        # vaccinations, rappels, sterilisations, castrations, identifications, tests fiv/felv, soins, deparasitages
        # if vtype is "soins" then we append the comment as visit description
        vtypes = [0, 0, 0, 0, 0, 0, 0, 0]
        comments = []
        # the QR code contains: ERA;<today's date>;<who authorized>;<authorization date>;<FAid>;<visit date>;<cat regs>;<vtypes joined as string>;<check>
        # check is a 12-byte string obtained by md5sum of previous part + some random junk + base64_encode + cut in half

        try:
            vdate = datetime.strptime(request.form["visit_date"], "%Y-%m-%d")
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
                    if theCat.owner.typeFAtemp():
                        FAname = theCat.temp_owner
                        FAid = "[{}]".format(FAname)
                    elif theCat.owner.typeAdoptes() or theCat.owner.typeHistorique():
                        FAname = None
                        FAid = "[{}]".format(theCat.owner_id)
                        PostAdoption = 1
                    else:
                        FAname = theCat.owner.FAname
                        FAid = theCat.owner.FAid

                # cumulate the information
                catlist.append(theCat)
                catregs.append(theCat.regStr())
                catvtypes.append(VisitType)

                if vetIsPrimo(VisitType):
                    vtypes[0] += 1
                if vetIsRappel1(VisitType):
                    vtypes[1] += 1
                if vetIsRappelAnn(VisitType):
                    vtypes[1] += 1
                if vetIsSteril(VisitType):
                    if theCat.sex == 2:
                        vtypes[3] += 1
                    else:
                        vtypes[2] += 1
                if vetIsIdent(VisitType):
                    vtypes[4] += 1
                if vetIsTest(VisitType):
                    vtypes[5] += 1
                if vetIsSoins(VisitType):
                    vtypes[6] += 1
                    if not comments:
                        # we also fix the comments so that newlines are respected
                        comments.append(Markup(escape(request.form["visit_comments"]).replace("\n","<br>")))
                if vetIsDepara(VisitType):
                    vtypes[7] += 1

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

        pdfname = "bon-veto-{}".format(FAname)
        return render_template("bonveto_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, bvtitle=pdfname, authFA=theAuthFA.FAname, cats=catlist, faname=FAname, postAD=PostAdoption, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    # action = generate bonVeto for unregistered cats
    # if catAccess == ACC_MOD and cmd == "fa_vetbonunreg":
    #     # generate the data for the bon using the provided info
    #     catlist = []
    #     catregs = []

    #     # if the name is empty, no field will appear in the bon
    #     FAname = request.form["visit_faname"]

    #     # vaccinations, rappels, sterilisations, castrations, identifications, tests fiv/felv, soins, deparasitages
    #     # if vtype is "soins" then we append the comment as visit description
    #     vtypes = [0, 0, 0, 0, 0, 0, 0, 0]
    #     comments = []
    #     # the QR code contains: ERA;<today's date>;<who authorized>;<authorization date>;<FAname>;<visit date>;<cat regs>;<vtypes joined as string>;<check>
    #     # check is a 12-byte string obtained by md5sum of previous part + some random junk + base64_encode + cut in half

    #     try:
    #         vdate = datetime.strptime(request.form["visit_date"], "%Y-%m-%d")
    #     except ValueError:
    #         vdate = datetime.now()

    #     # manage validation source and date
    #     theAuthFA = current_user
    #     authdate = datetime.now()

    #     # increment the number of the cat
    #     # TODO: get from db state table
    #     regnum = (authdate.year - 2000) * 10000 + 3000;

    #     # generate the vetinfo from the form
    #     VisitType = vetMapToString(request.form, "visit")

    #     # in this special case, we assume that "filled comments -> X type", so we force it
    #     if request.form["visit_comments"]:
    #         VisitType = VisitType[:6] + "X" + VisitType[7:]

    #     # iterate on the table to see how many cats to add
    #     for key in ("c1", "c2", "c3", "c4", "c5"):
    #         kage = key + "_age";
    #         age = int(request.form[kage])
    #         if age:
    #             # cat is defined, add the data
    #             urcat = {'regnum' : encodeRegnum(regnum) }
    #             catregs.append(encodeRegnum(regnum))
    #             regnum = regnum + 1

    #             ksex = key + "_sex"
    #             kcol = key + "_color"

    #             if age == 1:
    #                 urcat['age'] = "chaton"
    #             elif age == 2:
    #                 urcat['age'] = "chat"
    #             elif age == 3:
    #                 urcat['age'] = "chat age"

    #             if int(request.form[ksex]):
    #                 urcat['sex'] = TabSex[int(request.form[ksex])]

    #             if int(request.form[kcol]):
    #                 urcat['col'] = TabColor[int(request.form[kcol])]

    #             # forget about the name for now
    #             # urcat['name'] = ....

    #             # cumulate the information
    #             catlist.append(urcat)

    #             if vetIsPrimo(VisitType):
    #                 vtypes[0] += 1
    #             if vetIsRappel1(VisitType):
    #                 vtypes[1] += 1
    #             if vetIsRappelAnn(VisitType):
    #                 vtypes[1] += 1
    #             if vetIsSteril(VisitType):
    #                 if int(request.form[ksex]) == 2:
    #                     vtypes[3] += 1
    #                 else:
    #                     vtypes[2] += 1
    #             if vetIsIdent(VisitType):
    #                 vtypes[4] += 1
    #             if vetIsTest(VisitType):
    #                 vtypes[5] += 1
    #             if vetIsSoins(VisitType):
    #                 vtypes[6] += 1
    #                 if not comments:
    #                     # we also fix the comments so that newlines are respected
    #                     comments.append(Markup(escape(request.form["visit_comments"]).replace("\n","<br>")))
    #             if vetIsDepara(VisitType):
    #                 vtypes[7] += 1

    #         # if nothing was selected, return an error and stay here
    #         if not catlist:
    #             session["pendingmessage"] = [ [ 2, "Aucun chat selectionne" ] ]
    #             return redirect(url_for('unregpage'))

    #         # if no visit type was selected... same
    #         if sum(vtypes) == 0:
    #             session["pendingmessage"] = [ [ 2, "Aucune visite selectionnee" ] ]
    #             return redirect(url_for('unregpage'))

    #     bdate = datetime.today()

    #     # generate the qrcode string
    #     qrstr = "ERA;{};{};{};{};{};{};".format(bdate.strftime('%Y%m%d'), theAuthFA.FAid, authdate.strftime('%Y%m%d'), FAname, vdate.strftime('%Y%m%d'), "/".join(catregs), "".join(str(e) for e in vtypes))
    #     qrstr = qrstr + ERAsum(qrstr)

    #     pdfname = "bon-veto-{}".format(FAname)
    #     return render_template("bonveto_page.html", user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, bvtitle=pdfname, authFA=theAuthFA.FAname, ucats=catlist, faname=FAname, bdate=vdate, vtype=vtypes, comments=comments, qrdata=qrstr)

    # action = edit the vetvisits, deleting stuff etc. etc.
    if cmd == "fa_modvetdo":
        # get the cat
        catid = int(request.form["catid"])

        theCat = Cat.query.filter_by(id=catid).first();
        if theCat == None:
            return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="invalid cat id")

        if canAccessCat(theCat, current_user) != ACC_MOD:
            return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="cannot edit visits")

        vres = ""

        # start by deleting the selected visits
        for key in request.form.keys():
            if key[0:3] == 're_':
                vvid = int(key[3:])

                theVisit = VetInfo.query.filter_by(id=vvid).first()
                if theVisit == None:
                    return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="invalid vetvisit id")

                # paranoia check
                if theVisit.cat_id != theCat.id:
                    return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="vetivisit/cat mismatch")

                vres += " -E[{}]".format(theVisit.vtype)

                # we don't use deletevisit because the event message is completely wrong
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} du {} effacée".format(current_user.FAname, theVisit.vtype, theVisit.vdate.strftime('%d/%m/%y')))
                db.session.add(theEvent)
                db.session.delete(theVisit)

        # we now rebuild the vetshort by adding any preexisting info we were given
        # note that all old info is lost!
        vetstr = vetMapToString(request.form, "visit")

        # now iterate on the visits and cumulate
        for vv in theCat.vetvisits:
            if not vv.planned:
                vetstr = vetAddStrings(vetstr, vv.vtype)

        vres += " vs={}".format(vetstr)

        theCat.vetshort = vetstr
        db.session.commit()

        message = [ [0, "Informations mises a jour: {}".format(vres)] ]
        session["pendingmessage"] = message

        # return to cat page with update message
        return redirect(url_for('catpage') + "/" + request.form["catid"])

    # action = do nothing and return to cat page
    if cmd == "fa_modvetcancel":
        return redirect(url_for('catpage') + "/" + request.form["catid"])

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

    return render_template("error_page.html", user=current_user, errormessage="command error (/vet)")
