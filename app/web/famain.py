from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair, FAidSpecial
from app.models import User, Cat, VetInfo, Event
from app.helpers import cat_delete
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import and_
from datetime import datetime


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

        # decide which type of page to display
        mode = None
        if "otherMode" in session:
            mode = session["otherMode"]

            # these are only allowed for SV/ADM
            if (mode == "special-all" or mode == "special-adopt" or mode == "special-search") and not (current_user.FAisOV or current_user.FAisADM):
                mode = None

        # display current user pages or alternate user's?
        # we can see pages of other FAs if we are OV/ADM or we are the FA's resp
        FAid = current_user.id
        theFA = current_user
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
                theFA = current_user

        # handle special cases
        if mode == "special-vetplan":
            # query all vetinfo which are planned and associated with cats owned by the FA
            theVisits = VetInfo.query.filter(and_(VetInfo.doneby_id==FAid, VetInfo.planned==True)).order_by(VetInfo.vdate).all()

            return render_template("vet_page.html", devsite=devel_site, user=current_user, viewuser=theFA, visits=theVisits, FAids=FAidSpecial, msg=message)

        elif mode == "special-all":
            return render_template("list_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                listtitle="Tableau global des chats", catlist=Cat.query.order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message)

        elif mode == "special-adopt":
            return render_template("list_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                listtitle="Chats disponibles à l'adoption", catlist=Cat.query.filter_by(adoptable=True).order_by(Cat.regnum).all(), FAids=FAidSpecial, msg=message, adoptonly=True)

        elif mode == "special-search":
            searchfilter = session["searchFilter"]

            (src_name, src_regnum, src_id, src_FAname, src_mode) = searchfilter.split(';')

            # rules for search: OR mode always
            # name and id: substring searches
            # regnum: if nnn-yy then exact match, if nnn then startswith match
            cats = []

            if src_name:
                cats = cats + Cat.query.filter(Cat.name.contains(src_name)).all()

            if src_regnum:
                if src_regnum.find('-') != -1:
                    # exact match
                    rr = src_regnum.split('-')
                    rn = int(rr[0]) + 10000*int(rr[1])

                    cats = cats + Cat.query.filter_by(regnum=rn).all()

                elif src_regnum.isdigit():
                    # fix number, all years
                    clause = "NOT MOD (regnum-"+src_regnum+",10000)"
                    cats = cats + Cat.query.filter(clause).all()

            if src_id:
                cats = cats + Cat.query.filter(Cat.identif.contains(src_id)).all()

            if src_FAname:
                cats = cats + Cat.query.filter(Cat.temp_owner.contains(src_FAname)).all()

            max_regnum = db.session.query(db.func.max(Cat.regnum)).scalar()
            defaultvalues = [src_regnum, src_name, src_id, src_FAname];

            # we reuse the search page to display the list
            if src_mode == "select":
                return render_template("search_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    listtitle="Résultat de la recherche", scatlist=cats, FAids=FAidSpecial, msg=message, defval=defaultvalues, maxreg=max_regnum)
            else:
                return render_template("search_page.html", devsite=devel_site, user=current_user, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    listtitle="Résultat de la recherche", catlist=cats, FAids=FAidSpecial, msg=message, defval=defaultvalues, maxreg=max_regnum)

        # default list, which is not the same for FAs or Vets
        if theFA.FAisVET:
            # display the visits, sorted by FA

            visits = VetInfo.query.filter(and_(VetInfo.vet_id==FAid, and_(VetInfo.planned==True,VetInfo.transferred==True))).order_by(VetInfo.doneby_id).all()

            return render_template("main_page.html", devsite=devel_site, user=current_user, viewuser=theFA, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair,
                    vvisits=visits, FAids=FAidSpecial, msg=message)

        elif theFA.FAisFA:
            if FAid == FAidSpecial[4]:
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

    # check if you can access this
    if theCat.owner_id != current_user.id and not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data", FAids=FAidSpecial)
#        return redirect(url_for('fapage'))

    if cmd == "adm_histcat" and current_user.FAisADM:
        # move the cat to the historical list of cats
        newFA = User.query.filter_by(id=FAidSpecial[2]).first()
        theCat.owner.numcats -= 1
        newFA.numcats += 1
        theCat.owner_id = newFA.id
        theCat.adoptable = False
        theCat.lastop = datetime.now()
        session["pendingmessage"] = [ [0, "Chat {} déplacé dans l'historique".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré dans l'historique".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()

    if cmd == "adm_deletecat" and current_user.FAisADM:
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
