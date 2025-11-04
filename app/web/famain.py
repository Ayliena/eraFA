from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair, FAidSpecial, ACC_NONE, ACC_RO, ACC_MOD, ACC_FULL, ACC_TOTAL
from app.models import GlobalData, User, Cat, VetInfo, Event
from app.helpers import cat_delete, isFATemp, isRefuge, getViewUser, accessPrivileges
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import and_
from sqlalchemy.sql import text
from datetime import datetime,timedelta

@app.route('/fa', methods=["GET", "POST"])
def fapage():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    # generate the page
    if request.method == "GET":
        # handle any message
        if "pendingmessage" in session:
            message = session["pendingmessage"]
            session.pop("pendingmessage")
        else:
            message = []

        # display current user pages or alternate user's?
        FAid, theFA = getViewUser()

        if not theFA:
            return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

        catMode, vetMode, searchMode = accessPrivileges(theFA)

        # decide which type of page to display
        mode = None
        if "otherMode" in session:
            mode = session["otherMode"]

            # these are only allowed for SV/ADM
            if (mode == "special-all" or mode == "special-adopt") and searchMode == ACC_NONE:
                mode = None

            if mode == "special-search" and searchMode < ACC_FULL:
                mode = None

            # this is only allowed for VET
            if mode == "special-vethistory" and not current_user.FAisVET:
                mode = None

        # handle special cases
        if mode == "special-vetplan":
            # query all vetinfo which are planned and associated with cats owned by the FA
            theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==True)).order_by(VetInfo.vdate).all()

            vetAuth = (vetMode >= ACC_FULL)

            return render_template("vet_page.html", devsite=devel_site, user=current_user, viewuser=theFA, visits=theVisits, autoauth=vetAuth, canauth=vetAuth,
                                   FAids=FAidSpecial, msg=message)

        elif mode == "special-all":
            return render_template("list_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                listtitle="Tableau global des chats", catlist=Cat.query.order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message)

        elif mode == "special-adopt":
            return render_template("list_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                listtitle="Chats disponibles à l'adoption", catlist=Cat.query.filter_by(adoptable=True).order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message, adoptonly=True)

        elif mode == "special-vethistory":
            if "optVETOHIST" in session:
                histFilter = session["optVETOHIST"].split(';')
            else:
                histFilter = ["", (datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d'), datetime.today().strftime('%Y-%m-%d')]

            vquery = VetInfo.query
            # get all the visits
            vquery = vquery.filter(and_(VetInfo.vet_id==FAid, and_(VetInfo.planned==False,VetInfo.transferred==True)))
            # filter by fa if requested
            if histFilter[0]:
                vquery = vquery.join(VetInfo.doneby).filter(User.FAname.contains(histFilter[0]))

            for i in range(1,3):
                if histFilter[i]:
                    try:
                        dv = datetime.strptime(histFilter[i], "%Y-%m-%d")
                        dv = dv.replace(hour=23, minute=59, second=59)
                    except ValueError:
                        dv = None

                    if dv:
                        if i == 1:
                            vquery = vquery.filter(VetInfo.vdate>=dv)
                        elif i == 2:
                           vquery = vquery.filter(VetInfo.vdate<=dv)

            # display the past visits, sorted by date
            visits = vquery.order_by(VetInfo.vdate.desc()).all()

            return render_template("main_page.html", devsite=devel_site, user=current_user, viewuser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    vvisits=visits, visitmode="history", histfilter=histFilter, FAids=FAidSpecial, msg=message)

        elif mode == "special-search":
            searchfilter = session["searchFilter"]

            (src_name, src_regnum, src_id, src_FAname, src_mode) = searchfilter.split(';')

            # rules for search: OR mode always
            # name and id: substring searches
            # regnum: if nnn-yy then exact match, if nnn then startswith match
            cats = []

            if src_name:
                cats = cats + Cat.query.filter(Cat.name.contains(src_name)).order_by(Cat.regnum).all()

            if src_regnum:
                if src_regnum.startswith('N'):
                    # search for unreg cats
                    # no number provided: search for all
                    if src_regnum == 'N':
                        cid = -1
                    else:
                        try:
                            cid = int(src_regnum[1:])
                        except ValueError:
                            cid = -1

                    if cid < 0:
                        cats = cats + Cat.query.filter_by(regnum=cid).order_by(Cat.id).all()
                    else:
                        cats = cats + Cat.query.filter_by(id=cid).order_by(Cat.id).all()

                elif src_regnum.startswith('P'):
                    # search for private cats, same approach as above
                    if src_regnum == "P":
                        cid = -2
                    else:
                        try:
                            cid = int(src_regnum[1:])
                        except ValueError:
                            cid = -2

                    if cid < 0:
                        cats = cats + Cat.query.filter_by(regnum=cid).order_by(Cat.id).all()
                    else:
                        cats = cats + Cat.query.filter_by(id=cid).order_by(Cat.id).all()

                elif src_regnum.find('-') != -1:
                    # exact match
                    rr = src_regnum.split('-')
                    rn = int(rr[0]) + 10000*int(rr[1])

                    cats = cats + Cat.query.filter_by(regnum=rn).order_by(Cat.temp_owner,Cat.regnum).all()

                elif src_regnum.isdigit():
                    # fix number, all years
                    clause = "NOT MOD (regnum-"+src_regnum+",10000)"
                    cats = cats + Cat.query.filter(text(clause)).order_by(Cat.temp_owner,Cat.regnum).all()

            if src_id:
                cats = cats + Cat.query.filter(Cat.identif.contains(src_id)).order_by(Cat.temp_owner,Cat.regnum).all()

            if src_FAname:
                cats = cats + Cat.query.filter(Cat.temp_owner.contains(src_FAname)).order_by(Cat.temp_owner,Cat.regnum).all()

            # ok, so if multiple rules were provided, the results will NOT be sorted correctly, but it's too annoying to do this right
            globaldata = GlobalData.query.filter_by(id=1).first()
            max_regnum = "{}-{}".format(globaldata.LastImportReg%10000, int(globaldata.LastImportReg/10000))
            defaultvalues = [src_regnum, src_name, src_id, src_FAname];

            # we reuse the search page to display the list
            if src_mode == "select":
                return render_template("search_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    listtitle="Résultat de la recherche", scatlist=cats, FAids=FAidSpecial, msg=message, defval=defaultvalues, lastreg=max_regnum, lastdate=globaldata.LastImportDate, syncdate=globaldata.LastSyncDate)
            else:
                return render_template("search_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    listtitle="Résultat de la recherche", catlist=cats, FAids=FAidSpecial, msg=message, defval=defaultvalues, lastreg=max_regnum, lastdate=globaldata.LastImportDate, syncdate=globaldata.LastSyncDate)

        # default list, which is not the same for FAs or Vets
        if theFA.FAisVET:
            # display the visits, sorted by FA
            visits = VetInfo.query.filter(and_(VetInfo.vet_id==FAid, and_(VetInfo.planned==True,VetInfo.transferred==True))).order_by(VetInfo.doneby_id).all()

            return render_template("main_page.html", devsite=devel_site, user=current_user, viewuser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    vvisits=visits, visitmode="planned", FAids=FAidSpecial, msg=message)

        elif theFA.FAisFA or theFA.FAisREF or theFA.FAisAD or theFA.FAisDCD or theFA.FAisHIST:
            if isFATemp(FAid) or isRefuge(FAid):
                theCats = Cat.query.filter_by(owner_id=FAid).order_by(Cat.temp_owner,Cat.regnum).all()
            else:
                theCats = Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all()

            return render_template("main_page.html", devsite=devel_site, user=current_user, viewuser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    cats=theCats, FAids=FAidSpecial, msg=message)

        else:
            # display empty page
            return render_template("main_page.html", devsite=devel_site, user=current_user, viewuser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                   FAids=FAidSpecial, msg=message)

    # handle POST commands
    cmd = request.form["action"]

    # alternate GET command for another FA
    if cmd == "sv_fastate":
        FAid = int(request.form["FAid"]);
        # note: we do not perform any check on the validity of FAid or on the access privileges,
        # since they will be performed by the GET method

        session["otherMode"] = None
        session["otherFA"] = FAid
        return redirect(url_for('fapage'))

    # get the cat
    theCat = Cat.query.filter_by(id=request.form["catid"]).first()
    if theCat == None:
        return render_template("error_page.html", user=current_user, errormessage="invalid cat id", FAids=FAidSpecial)
        return redirect(url_for('fapage'))

    catMode, vetMode, searchMode = accessPrivileges(theCat.owner)

    # check if you can access this
    if catMode != ACC_TOTAL:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data", FAids=FAidSpecial)
#        return redirect(url_for('fapage'))

    if cmd == "adm_histcat":
        # move the cat to the historical list of cats
        newFA = User.query.filter_by(id=FAidSpecial[2]).first()
        theCat.owner.numcats -= 1
        newFA.numcats += 1
        theCat.owner_id = newFA.id
        theCat.temp_owner = ""
        theCat.adoptable = False
        # delete all the planned visits
        VetInfo.query.filter(and_(VetInfo.cat_id == theCat.id, VetInfo.planned == True)).delete()
        theCat.lastop = datetime.now()
        session["pendingmessage"] = [ [0, "Chat {} déplacé dans l'historique".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré dans l'historique".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()

    if cmd == "adm_deletecat":
        # erase the cat and all the associated information from the database
        # NOTE THAT THIS IS IRREVERSIBLE AND LEAVES NO TRACE
        session["pendingmessage"] = [ [0, "Chat {} effacé du systeme".format(theCat.asText())] ]

        cat_delete(theCat)

        current_user.FAlastop = datetime.now()
        db.session.commit()

    return redirect(url_for('fapage'))


@app.route("/self")
@login_required
def selfpage():
    # a version of the main page which brings you back to your list
    session.pop("otherFA", None)
    session.pop("otherMode", None)
    session.pop("searchFilter", None)
    return redirect(url_for('fapage'))
