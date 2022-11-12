from app import app, db, devel_site
from app.staticdata import FAidSpecial, DBTabColor, ACC_NONE, ACC_RO, ACC_MOD, ACC_FULL, ACC_TOTAL, NO_VET, GEN_VET
from app.models import  Cat, User, Event, VetInfo
from app.helpers import cat_delete, decodeRegnum, vetAddStrings, accessPrivileges
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import and_
from sqlalchemy.sql import text
from datetime import datetime


@app.route("/search", methods=["GET", "POST"])
@login_required
def searchpage():
    catMode, vetMode, searchMode = accessPrivileges(current_user)

    if searchMode < ACC_FULL:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges", FAids=FAidSpecial)

    max_regnum = db.session.query(db.func.max(Cat.regnum)).scalar()

    if request.method == "GET":
        # generate the search page
        return render_template("search_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, maxreg=max_regnum)

    cmd = request.form["action"]

    if cmd == "adm_search" or cmd == "adm_searchs":
        src_name = request.form["src_name"]
        src_regnum = request.form["src_regnum"]
        src_id = request.form["src_id"]
        src_FAname = request.form["src_faname"]
        src_mode = "info" if cmd == "adm_search" else "select"

        # if they are all empty => complain
        if not src_name and not src_regnum and not src_id and not src_FAname:
            message = [ [3, "Il faut indiquer au moins un critere de recherche!" ] ]
            return render_template("search_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, msg=message, maxreg=max_regnum)

        # if regnum ends with '-', remove it, if it starts with '-', refuse it
        while src_regnum.endswith('-'):
            src_regnum = src_regnum[:-1]

        if src_regnum.startswith('-'):
            message = [ [3, "Le numero de registre ne peut pas commencer par '-'!" ] ]
            return render_template("search_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, msg=message, maxreg=max_regnum)

        session["otherMode"] = "special-search"
        session["searchFilter"] = src_name+";"+src_regnum+";"+src_id+";"+src_FAname+";"+src_mode
        return redirect(url_for('fapage'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/search)", FAids=FAidSpecial)


@app.route("/admin", methods=["GET", "POST"])
@login_required
def adminpage():
    if not current_user.FAisADM:
        return redirect(url_for('fapage'))

    if request.method == "GET":
        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial)

    cmd = request.form["action"]

    # generate an empty page for the addition of a Refu dossier (navbar use)
    if cmd == "adm_refucat":
        return redirect(url_for('refupage'))

    if cmd == "adm_admin":
        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial)

    if cmd == "adm_numcats":
        s = text('UPDATE users SET numcats = ( SELECT COUNT(regnum) AS "Count" FROM cats WHERE cats.owner_id = users.id );')
        db.engine.execute(s)
        db.session.commit()

        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Nombre de chats mis a jour")

    if cmd == "adm_vettab":
        vets = User.query.filter_by(FAisVET=True).all()
        msg = ''
        for v in vets:
            msg += "'{}' => {}, ".format('inconnu' if (v.id == NO_VET or v.id == GEN_VET) else v.FAid, v.id)

        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult=msg)

    if cmd == "adm_deluser":
        u_name = request.form["u_name"]
        if not u_name:
            return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Aucun nom specifie")

        # find the user
        theFA = User.query.filter_by(username=u_name).first()

        if not theFA:
            return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Aucun utilisateur s'appelle '{}'".format(u_name))

        # make sure we don't regret this
        if theFA.id in FAidSpecial:
            return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Impossible d'effacer un utilisateur special")

        # this is problematic, but in general adding a vet here means it's in Refugilys as well, so it must stay
        if theFA.FAisVET:
            return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Effacer un veterinaire doit se faire manuellement".format(u_name))

        # for all cats owned by the user:
        #   set all visits done by the user to "FA temporaires"
        #   set temp_owner to be UC / swapped FAname
        #   move the cat to FA temporaires

        FAtemp = User.query.filter_by(id=FAidSpecial[4]).first()

        # manipulate the FA name attempting to turn it into something Refu-friendly
        nn = (theFA.FAname.upper()).split()
        nn.append(nn.pop(0))
        tempname = " ".join(nn)

        msg = "Conversion nom: {} -> {}, chats transferes:".format(theFA.FAname, tempname)

        # move all the cats to FA_temp
        cats = Cat.query.filter_by(owner_id=theFA.id).all()

        for c in cats:
            msg += " {}".format(c.regStr())


            # we shift the visits and also kill any authorization, which is useless anyway
            for vv in c.vetvisits:
                vv.doneby_id = FAidSpecial[4]
                vv.validby_id = None

            # modify the FA
            # generate the event
            theEvent = Event(cat_id=c.id, edate=datetime.now(), etext="{}: transféré de {} a {}[{}] (userdel)".format(current_user.FAname, c.owner.FAname, FAtemp.FAname, tempname))
            db.session.add(theEvent)

            FAtemp.numcats += 1
            c.owner_id = FAtemp.id
            c.temp_owner = tempname
            c.lastop = datetime.now()
            db.session.commit()

        # some vet visits on historical cats may still be associated to this FA, relink them to FA_temp
        # as above, kill any authorization
        vetvisits = VetInfo.query.filter_by(doneby_id=theFA.id).all()

        for vv in vetvisits:
            vv.doneby_id = FAidSpecial[4]
            vv.validby_id = None

        # now delete the user
        db.session.delete(theFA)
        current_user.FAlastop = datetime.now()
        db.session.commit()

        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult=msg)

    if cmd == "adm_delvisits":
        regnum = request.form["c_regnum"]
        theCat = None

        rn = decodeRegnum(regnum)
        if rn > 0:
            theCat = Cat.query.filter_by(regnum=rn).first()

        elif regnum.startswith('N'):
            # check for an unregistered N cat
            try:
                catid = int(regnum[1:])
            except ValueError:
                catid = -1

            if catid > 0:
                theCat = Cat.query.filter_by(id=catid).first()

        if not theCat:
            return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Chat {} non trouve".format(request.form["c_regnum"]))

        VetInfo.query.filter_by(cat_id=theCat.id).delete()
        theCat.vetshort = "--------"

        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: remise a zero des visites veterinaires".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        theCat.lastop = datetime.now()
        db.session.commit()

        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Visites du {} effacees".format(theCat.regStr()))

    if cmd == "adm_revetsh":
        rn = decodeRegnum(request.form["c_regnum"])
        if rn == -1:
            return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Format du numero de registre incorrect")

        # 0-00 is a special request to regen all
        if rn == 0:
            catlist = Cat.query.all()

            for theCat in catlist:
                theCat.vetshort = "--------"
                for vv in theCat.vetvisits:
                    theCat.vetshort = vetAddStrings(theCat.vetshort, vv.vtype)

        else:
            theCat = Cat.query.filter_by(regnum=rn).first()
            if not theCat:
                return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Chat {} non trouve".format(request.form["c_regnum"]))

            theCat.vetshort = "--------"
            for vv in theCat.vetvisits:
                theCat.vetshort = vetAddStrings(theCat.vetshort, vv.vtype)

        # note that we add no event, AND the lastop of the cat is not updated, since no data has really changed
        current_user.FAlastop = datetime.now()

        db.session.commit()

        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult="Sommaire des visites du {} regenere".format(theCat.regStr()))

    if cmd == "adm_cleanup":
        # we do this manually by iterating on all the "historique" cats

        # determine current year and define the beginning of the current year
        curryear = datetime.now().year

        # get the cats, of course any cat which has arrived this year is automatically excluded
        cats = Cat.query.filter(and_(Cat.owner_id==FAidSpecial[2], Cat.regnum<(curryear*10000))).all()

        msg = "Chats effaces:"

        # iterate on all cats and check the vet visits, if they all are BEFORE the current year, we can safely delete it
        for c in cats:
            to_del = True

            for vv in c.vetvisits:
                if vv.vdate.year >= curryear:
                    to_del = False
                    break

            if to_del:
                # delete the cat
                cat_delete(c)
                msg += " " + c.regStr()

        db.session.commit()

        return render_template("admin_page.html", devsite=devel_site, user=current_user, FAids=FAidSpecial, admresult=msg)

    return render_template("error_page.html", user=current_user, errormessage="command error (/admin)", FAids=FAidSpecial)


@app.route("/unreg", methods=["POST", "GET"])
@login_required
def unregpage():
    catMode, vetMode, searchMode = accessPrivileges(current_user)

    if searchMode != ACC_TOTAL:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges", FAids=FAidSpecial)

    # handle any message
    if "pendingmessage" in session:
        message = session["pendingmessage"]
        session.pop("pendingmessage")
    else:
        message = []

    # get or post adm_unreg are the same
    # generate the unreg management page (for now, only gen bon veto)
    if request.method == "GET" or (request.method == "POST" and request.form["action"] == "adm_unreg"):
        return render_template("unreg_page.html", devsite=devel_site, user=current_user, msg=message, FAids=FAidSpecial, TabCols=DBTabColor)

    cmd = request.form["action"]

    return render_template("error_page.html", user=current_user, errormessage="command error (/unreg)", FAids=FAidSpecial)


@app.route("/help")
@login_required
def helppage():
    return render_template("help_page.html", user=current_user, FAids=FAidSpecial)
