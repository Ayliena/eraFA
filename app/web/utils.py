from app import app, db
from app.staticdata import FAidSpecial
from app.models import  Cat, User, Event, VetInfo
from app.helpers import cat_delete
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import and_
from sqlalchemy.sql import text
from datetime import datetime


@app.route("/search", methods=["GET", "POST"])
@login_required
def searchpage():
    if not current_user.FAisADM and not current_user.FAisOV:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges", FAids=FAidSpecial)

    if request.method == "GET":
        # generate the search page
        max_regnum = db.session.query(db.func.max(Cat.regnum)).scalar()

        return render_template("search_page.html", user=current_user, FAids=FAidSpecial, maxreg=max_regnum)

    cmd = request.form["action"]

    if cmd == "adm_search":
        src_name = request.form["src_name"]
        src_regnum = request.form["src_regnum"]
        src_id = request.form["src_id"]

        # if they are all empty => complain
        if not src_name and not src_regnum and not src_id:
            message = [ [3, "Il faut indiquer au moins un critere de recherche!" ] ]
            return render_template("search_page.html", user=current_user, FAids=FAidSpecial, msg=message)

        session["otherMode"] = "special-search"
        session["searchFilter"] = src_name+";"+src_regnum+";"+src_id
        return redirect(url_for('fapage'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/search)", FAids=FAidSpecial)


@app.route("/admin", methods=["GET", "POST"])
@login_required
def adminpage():
    if not current_user.FAisADM:
        return redirect(url_for('fapage'))

    if request.method == "GET":
        return render_template("admin_page.html", user=current_user, FAids=FAidSpecial)

    cmd = request.form["action"]

    # generate an empty page for the addition of a Refu dossier (navbar use)
    if cmd == "adm_refucat":
        return redirect(url_for('refupage'))

    if cmd == "adm_admin":
        return render_template("admin_page.html", user=current_user, FAids=FAidSpecial)

    if cmd == "adm_numcats":
        s = text('UPDATE users SET numcats = ( SELECT COUNT(regnum) AS "Count" FROM cats WHERE cats.owner_id = users.id );')
        db.engine.execute(s)
        db.session.commit()

        return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult="Nombre de chats mis a jour")

    if cmd == "adm_vettab":
        vets = User.query.filter_by(FAisVET=True).all()
        msg = ''
        for v in vets:
            msg += "'{}' => {}, ".format('inconnu' if v.username=='genvet' else v.FAid, v.id)

        return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult=msg)

    if cmd == "adm_deluser":
        u_name = request.form["u_name"]
        if not u_name:
            return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult="Aucun nom specifie")

        # find the user
        theFA = User.query.filter_by(username=u_name).first()

        if not theFA:
            return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult="Aucun utilisateur s'appelle '{}'".format(u_name))

        # make sure we don't regret this
        if theFA.id in FAidSpecial:
            return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult="Impossible d'effacer un utilisateur special")

        # this is problematic, but in general adding a vet here means it's in Refugilys as well, so it must stay
        if theFA.FAisVET:
            return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult="Effacer un veterinaire doit se faire manuellement".format(u_name))

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

        cats = Cat.query.filter_by(owner_id=theFA.id).all()

        for c in cats:
            msg += " {}".format(c.regStr())

            c.temp_owner = tempname

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
            c.lastop = datetime.now()
            db.session.commit()

        # now delete the user
        db.session.delete(theFA)
        current_user.FAlastop = datetime.now()
        db.session.commit()

        return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult=msg)

    if cmd == "adm_delvisits":
        c_regnum = request.form["c_regnum"]
        if c_regnum.find('-') == -1:
            return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult="Format du numero de registre incorrect")

        # exact match
        rr = c_regnum.split('-')
        rn = int(rr[0]) + 10000*int(rr[1])
        theCat = Cat.query.filter_by(regnum=rn).first()

        VetInfo.query.filter_by(cat_id=theCat.id).delete()
        theCat.vetshort = "--------"

        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: remise a zero des visites veterinaires".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()

        return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult="Visites du {} effacees".format(theCat.regStr()))

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

        return render_template("admin_page.html", user=current_user, FAids=FAidSpecial, admresult=msg)

    return render_template("error_page.html", user=current_user, errormessage="command error (/admin)", FAids=FAidSpecial)


@app.route("/help")
@login_required
def helppage():
    return render_template("help_page.html", user=current_user, FAids=FAidSpecial)
