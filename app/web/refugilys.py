from app import app, db
from app.staticdata import TabColor, TabSex, TabHair, DBTabColor, DBTabSex, DBTabHair, FAidSpecial
from app.models import User, Cat, VetInfo, Event
from app.helpers import vetAddStrings
from flask import render_template, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from datetime import datetime, timedelta


@app.route("/refu", methods=["GET", "POST"])
@login_required
def refupage():
    if not current_user.FAisADM:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges", FAids=FAidSpecial)

    if request.method == "GET":
        # generate the empty page with random filtering (for now)
        mdate = datetime.now() + timedelta(days=-7)
        cats = Cat.query.filter(Cat.lastop>=mdate).all()
        return render_template("refu_page.html", user=current_user, mdate=mdate, modcats=cats, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    cmd = request.form["action"]

    if cmd == "adm_modfilter":
        try:
            mdate = datetime.strptime(request.form["mod_date"], "%d/%m/%y")
        except ValueError:
            mdate = datetime.now()

        cats = Cat.query.filter(Cat.lastop>=mdate).order_by(Cat.lastop.desc()).all()
        return render_template("refu_page.html", user=current_user, mdate=mdate, modcats=cats, FAids=FAidSpecial, tabcol=TabColor, tabsex=TabSex, tabhair=TabHair)

    if cmd == "adm_refuexport":
#        return jsonify(request.form.to_dict())

        # this is potentially dangerous, if someone messes with the date, does not filter and then exports
        # but the only consequence is missing data, so I don't care
        try:
            mdate = datetime.strptime(request.form["mod_date"], "%d/%m/%y")
        except ValueError:
            mdate = datetime.now()

        cats = Cat.query.filter(Cat.lastop>=mdate).order_by(Cat.regnum).all()

        datfile = []

        for cat in cats:
            if "re_{}".format(cat.id) in request.form:
                comments = cat.comments.replace("\r",'')
                comments = comments.replace("\n","<EOL>")

                faname = cat.owner.username if not cat.owner_id == FAidSpecial[4] else "[{}]".format(cat.temp_owner)

                datline = [ cat.regStr(), faname, cat.name, cat.identif, DBTabSex[cat.sex],
                            ("" if not cat.birthdate else cat.birthdate.strftime('%d/%m/%y') ),
                            DBTabHair[cat.longhair], DBTabColor[cat.color], comments]

                for vv in cat.vetvisits:
                    datline.extend([ ("VP" if vv.planned else "VE"), vv.vtype, vv.vdate.strftime('%d/%m/%y'), str(vv.vet_id), vv.doneby.username ])

                datline.append("EOD")

                datfile.append(";".join(datline))

        return Response(
            "\n".join(datfile),
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=faweb-export.dat"})

    if cmd == "adm_refuexpall":
        # filter out --historique--???
        cats = Cat.query.order_by(Cat.regnum).all()

        datfile = []

        for cat in cats:
            comments = cat.comments.replace("\r",'')
            comments = comments.replace("\n","<EOL>")

            faname = cat.owner.username if not cat.owner_id == FAidSpecial[4] else "[{}]".format(cat.temp_owner)

            datline = [ cat.regStr(), faname, cat.name, cat.identif, DBTabSex[cat.sex],
                        ("" if not cat.birthdate else cat.birthdate.strftime('%d/%m/%y') ),
                        DBTabHair[cat.longhair], DBTabColor[cat.color], comments]

            for vv in cat.vetvisits:
                datline.extend([ ("VP" if vv.planned else "VE"), vv.vtype, vv.vdate.strftime('%d/%m/%y'), str(vv.vet_id), vv.doneby.username ])

            datline.append("EOD")

            datfile.append(";".join(datline))

        return Response(
            "\n".join(datfile),
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=faweb-dbase.dat"})

    if cmd == "adm_refuimport":
        # iterate on all the lines one by one
        # if a registre already exists, skip it (no update)
        msg = [ [1, "Resultats de l'import" ] ]

        if "r_dossier" in request.form:
            lines = request.form["r_dossier"].splitlines()

            for l in lines:
                v = l.split(';')

                if len(v) < 9:
                    msg.append([3, "Format erroné: {} (len={})".format(l, len(v)) ])
                    continue

                # if the regnum starts with * then it means we are editing an existing cat
                # in this case information is not completed, it's overwritten and vet visits
                # are edited as well
                editmode = False
                registre = v[0]
                if registre[0] == '*':
                    editmode = True
                    registre = registre[1:]

                # check if registre exists
                rr = registre.split('-')
                rn = int(rr[0]) + 10000*int(rr[1])

                # extract all the non-vet info so that we can update empty fields
                r_name = v[2]
                r_id = v[3]

                # convert fields to DB format (sex/hairlength/color)
                r = [index for index, value in enumerate(DBTabSex) if value == v[4]]
                if r:
                    r_sex = r[0]
                else:
                    r_sex = 0

                r = [index for index, value in enumerate(DBTabHair) if value == v[6]]
                if r:
                    r_hl = r[0]
                else:
                    r_hl = 0

                r = [index for index, value in enumerate(DBTabColor) if value == v[7]]
                if r:
                    r_col = r[0]
                else:
                    r_col = 0

                # convert birthdate
                try:
                    r_bd = datetime.strptime(v[5], "%d/%m/%y")
                except ValueError:
                    r_bd = None

                r_comm = v[8].replace("<EOL>", "\n")

                # see if we already have this
                theCat = Cat.query.filter_by(regnum=rn).first();

                # locate the FA, using the username
                # note that editmode can work with special FAs
                # we also handle the special case of temp FAs (recognized by the '[]' around the name)
                faname = v[1];
                temp_faname = ''
                if faname and faname[0] == '[' and faname[-1] == ']':
                    # temp fa
                    theFA = User.query.filter_by(id=FAidSpecial[4]).first()
                    temp_faname = faname[1:-1]
                else:
                    # normal (or special) FA
                    if editmode:
                        theFA = User.query.filter_by(username=faname).first()
                    else:
                        theFA = User.query.filter(and_(User.username==faname, or_(User.FAisFA==True,User.FAisREF==True))).first()

                # make sure that we have the FA
                if not theFA:
                    if editmode:
                        # assume it's the old one, in any case it's not like we can edit anything....
                        if faname:
                            # this means we wanted to move it, but the FA doesn't exist
                            msg.append([2, "{}: FA '{}' inexistente, le chat va rester dans la famille actuelle".format(registre, faname)])

                        theFA = theCat.owner

                    else:
                        # we need to define a FA, so we use the current user
                        msg.append([2, "{}: FA '{}' non trouvée, rajoute ici".format(registre, v[1]) ])
                        theFA = current_user

                # decode the table of vet visits
                offs = 9
                vvisits = []
                formaterror = False
                r_vetshort = '--------'

                while (v[offs] and v[offs] != 'EOD'):
                    if offs+5 > len(v):
                        msg.append([3, "Format erroné: {} (truncated vet info at offs {})".format(l, offs) ])
                        formaterror = True
                        break

                    v_planned = (v[offs] == 'VP')
                    v_type = v[offs+1]
                    # convert date
                    try:
                        v_date = datetime.strptime(v[offs+2], "%d/%m/%y")
                    except ValueError:
                        msg.append([3, "Format erroné: {} (invalid vdate at offs {})".format(l, offs) ])
                        formaterror = True
                        break

                    v_id = int(v[offs+3])
                    # validate vet id
                    vet = User.query.filter(and_(User.id==v_id,User.FAisVET==True)).first()
                    if not vet:
                        msg.append([3, "Format erroné: {} (invalid vet_id at offs {})".format(l, offs) ])
                        formaterror = True
                        break

                    # this is a complete mess, since there's no way to know WHICH FA has done the visit
                    # if the line specifies 'FA' we use the current (new FA)
                    # in all other cases AND for temporary FAs, we use the REF
                    # exception: if the visit is planned then always associate with the current FA
                    v_doneby = FAidSpecial[3]
                    if (v[offs+4] == 'FA' and not theFA.id == FAidSpecial[4]) or v_planned:
                        v_doneby = theFA.id

                    # all is good, cumulate vetinfo and prepare the object, cat_id will be invalid for now
                    if not v_planned:
                        r_vetshort = vetAddStrings(r_vetshort, v_type)

                    vvisits.append( VetInfo(doneby_id=v_doneby, vet_id=v_id, vtype=v_type, vdate=v_date, planned=v_planned) )
                    offs += 5

                # in case of format error, do nothing except spitting out the error message
                if formaterror:
                    continue

                # we now operate in two completely different ways depending if the cat is already in the
                # database or not and we are in edit mode or not

                if theCat == None and editmode:
                    msg.append([3, "Tentatif de mise a jour du {}, qui N'EST PAS dans la base de donnees!".format(registre) ])
                    continue

                if theCat != None and editmode:
                    # ok, we update the info here

                    # NOTE: in edit mode an empty fields means "leave data alone" and does not mean "erase data"
                    # info is Adopt Name Ident Sex Birthdate L(hairlen) Color (c)omments Description Picture
                    updated = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-']

                    if r_name and theCat.name != r_name:
                        theCat.name = r_name
                        updated[1] = 'N'

                    if r_id and theCat.identif != r_id:
                        theCat.identif = r_id
                        updated[2] ='I'

                    if r_sex and theCat.sex != r_sex:
                        theCat.sex = r_sex
                        updated[3] = 'S'

                    if r_bd and theCat.birthdate != r_bd:
                        theCat.birthdate = r_bd
                        updated[4] = 'B'

                    if r_hl and theCat.longhair != r_hl:
                        theCat.longhair = r_hl
                        updated[5] = 'L'

                    if r_col and theCat.color != r_col:
                        theCat.color = r_col
                        updated[6] = 'C'

                    if r_comm and theCat.comments != r_comm:
                        theCat.comments = r_comm
                        updated[7] = 'c'

                    # indicate moodification of the data
                    updated = "".join(updated)

                    if updated != "----------":
                        msg.append([1, "Numéro de registre {} mis a jour: {}".format(registre, updated)])
                        theCat.lastop = datetime.now()

                        # generate an event
                        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: informations mises a jour (Refugilys): {}".format(current_user.FAname, updated))
                        db.session.add(theEvent)

                    # update the FA if modified (note that here theFA is always defined!)
                    if faname:
                        msg.append([0, "Numéro de registre {} deplace de {} vers {}{}".format(registre, theCat.owner.FAname, theFA.FAname, faname if theFA.id == FAidSpecial[4] else '') ])
                        theCat.lastop = datetime.now()

                        # generate an event
                        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: FA mise a jour (Refugilys): {} -> {}".format(current_user.FAname, theCat.owner.FAname, theFA.FAname))
                        db.session.add(theEvent)

                        # update the FA by moving the cat
                        theCat.owner.numcats -= 1
                        theCat.owner_id = theFA.id
                        theFA.numcats += 1

                        # if we are moving TO a tempFA, update the name
                        if theFA.id == FAidSpecial[4]:
                            theCat.temp_owner = temp_faname

                        # if the destination FA is any of dead/adopted/historical then clear the adopted flag and clear the fa name
                        if theFA.id == FAidSpecial[0] or theFA.id == FAidSpecial[1] or theFA.id == FAidSpecial[2]:
                            theCat.adoptable = False
                            theCat.temp_owner = ""

                        # reassociate any planned visit and clear any validation
                        theVisits = VetInfo.query.filter(and_(VetInfo.cat_id == theCat.id, VetInfo.planned == True)).all()
                        for v in theVisits:
                            v.doneby_id = theFA.id
                            v.validby_id = None

                    # associate the vet visits
                    for vv in vvisits:
                        vv.cat_id = theCat.id
                        db.session.add(vv)

                    if r_vetshort != '--------':
                        msg.append([0, "Numéro de registre {} mis a jour: visites {}".format(registre, r_vetshort)])
                        theCat.vetshort = vetAddStrings(theCat.vetshort, r_vetshort)
                        theCat.lastop = datetime.now()
                        # generate an event
                        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: Visites mises a jour (Refugilys): {}".format(current_user.FAname, r_vetshort))
                        db.session.add(theEvent)

                    # should be done only if we updated something?
                    db.session.commit()
                    continue

                # if we reach here then editmode == False
                if theCat != None:
                    # this is update mode, vet data is ignored but any missing information which is available
                    # in the input is used to update the database

                    # info is Adoppt Name Ident Sex Birthdate L(hairlen) Color (c)omments Description Picture
                    updated = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-']

                    # note that only some data can be updated (adopt/desc/vetinfo can't, for example)
                    if not theCat.name and r_name:
                        theCat.name = r_name
                        updated[1] = 'N'

                    if not theCat.identif and r_id:
                        theCat.identif = r_id
                        updated[2] ='I'

                    if not theCat.sex and r_sex:
                        theCat.sex = r_sex
                        updated[3] = 'S'

                    if not theCat.birthdate and r_bd:
                        theCat.birthdate = r_bd
                        updated[4] = 'B'

                    if not theCat.longhair and r_hl:
                        theCat.longhair = r_hl
                        updated[5] = 'L'

                    if not theCat.color and r_col:
                        theCat.color = r_col
                        updated[6] = 'C'

                    if not theCat.comments and r_comm:
                        theCat.comments = r_comm
                        updated[7] = 'c'

                    # indicate moodification of the data
                    updated = "".join(updated)

                    if updated != "----------":
                        msg.append([2, "Numéro de registre {} déjà présent, informations rajoutees: {}".format(registre, updated)])
                        db.session.commit()
                    else:
                        msg.append([2, "Numéro de registre {} déjà présent, aucune nouvelle information, dossier ignoré".format(registre) ])

                    if not theFA:
                        msg.append([3, "Numéro de registre {} déjà présent et FA '{}' non trouvee!".format(registre, v[1]) ])
                    else:
                        if theCat.owner_id != theFA.id:
                            msg.append([3, "Numéro de registre {} déjà présent mais dans une autre FA (il est chez {}, on veut le rajouter chez {})!".format(registre, theCat.owner.FAname, theFA.FAname) ])
                    continue

                # now take care of the vetvisits
                # create the cat
                theCat = Cat(regnum=rn, owner_id=theFA.id, temp_owner=temp_faname, name=r_name, sex=r_sex, birthdate=r_bd, color=r_col, longhair=r_hl, identif=r_id,
                        vetshort=r_vetshort, comments=r_comm, description='', adoptable=False)

                db.session.add(theCat)
                theFA.numcats += 1

                # make sure we have an id
                db.session.commit()

                # associate the vet visits
                for vv in vvisits:
                    vv.cat_id = theCat.id
                    db.session.add(vv)

                # generate the event
                msg.append( [0, "Chat {} importé de Refugilys chez {}".format(registre, theFA.FAname) ] )
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: importé de Refugilys".format(current_user.FAname))
                db.session.add(theEvent)

        current_user.FAlastop = datetime.now()
        db.session.commit()

        session["pendingmessage"] = msg
        return redirect(url_for('fapage'))

    return render_template("error_page.html", user=current_user, errormessage="command error (/refu)", FAids=FAidSpecial)
#    return redirect(url_for('refupage'))
