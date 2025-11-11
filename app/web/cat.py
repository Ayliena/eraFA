from app import app, db, devel_site
from app.staticdata import DBTabColor, TabCage, FAidSpecial, ACC_NONE, ACC_RO, ACC_FULL, ACC_TOTAL, DEFAULT_VET
from app.models import User, Cat, VetInfo, Event
from app.helpers import isRefuge, isFATemp, isValidCage, cat_associate_to_FA, accessPrivileges, getViewUser
from app.vetvisits import vetMapToString, vetSubStrings, cat_addVetVisit, cat_updateVetVisit
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime
import os
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename
import re


@app.route("/cat", methods=["POST"])
@app.route('/cat/<int:catid>', methods=["GET"])
@login_required
def catpage(catid=-1):
    if request.method == "GET":
        if catid == -1:
            return redirect(url_for('fapage'))

        # we simulate a post request with action = fa_viewcat
        cmd = 'fa_viewcat'

    elif request.method == "POST":
        cmd = request.form["action"]

        if "catid" in request.form and request.form["catid"] != 'None':
            catid = int(request.form["catid"])

    if cmd == "fa_return":
        return redirect(url_for('fapage'))

    # this is to get the overall power of the user for the initial operations
    catMode, vetMode, searchMode = accessPrivileges(current_user)

    # generate an empty page to add a new cat
    if cmd == "adm_newcat":
        if catMode == ACC_TOTAL:
            theCat = Cat(regnum=0,temp_owner="")
            return render_template("cat_page.html", devsite=devel_site, user=current_user, cat=theCat, falist=User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).order_by(User.FAid).all(),
                                   FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)
        else:
            return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="insufficient privileges to add cat (adm)", FAids=FAidSpecial)

    # special version for REF user (unregistered cat)
    if cmd == "adm_newcatref":
        if catMode >= ACC_FULL:
            theCat = Cat(regnum=0,owner_id=current_user.id,temp_owner="AXX")
            return render_template("cat_page.html", user=current_user, cat=theCat,
                                   FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)
        else:
            return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="insufficient privileges to add cat (ref)", FAids=FAidSpecial)

    # add a cat here or in a specific FA
    if cmd == "adm_addcathere" or cmd == "adm_addcatputFA":
        if (cmd == "adm_addcathere" and catMode >= ACC_FULL) or (cmd == "adm_addcatputFA" and catMode == ACC_TOTAL):
            # generate the new cat using the form information
            vetstr = vetMapToString(request.form, "visit")

            try:
                bdate = datetime.strptime(request.form["c_birthdate"], "%Y-%m-%d")
            except ValueError:
                bdate = None

            # convert registre, for a NE cat, we just use -1
            rv = request.form["c_registre"] if "c_registre" in request.form else ""
            if rv == "":
                rn = -1
            else:
                rr = rv.split('-')
                rn = int(rr[0]) + 10000*int(rr[1])

            fatemp = request.form["c_cage"] if current_user.FAisREF else request.form["c_fatemp"]

            theCat = Cat(regnum=rn, temp_owner=fatemp, name=request.form["c_name"], sex=request.form["c_sex"], birthdate=bdate,
                        color=request.form["c_color"], longhair=request.form["c_hlen"], identif=request.form["c_identif"].upper(),
                        description=request.form["c_description"], comments=request.form["c_comments"], vetshort=vetstr,
                        adoptable=(request.form["c_adoptable"]=="1"))

            # for valid regnums, make sure that we're not adding a duplicate
            if rn > 0:
                # ensure that registre is unique
                checkCat = Cat.query.filter_by(regnum=rn).first()

                if checkCat:
                    # this is bad, we regenerate the page wit the current data
                    message = [ [3, "Le numéro de registre existe déjà!"] ]
                    theCat.regnum = 0
                    return render_template("cat_page.html", devsite=devel_site, user=current_user, cat=theCat, falist=User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).order_by(User.FAid).all(), msg=message,
                                           FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)

            # validate the id
            if theCat.identif:
                # this must either be [0-9]{15} or [A-Za-z]{3}[0-9]{3}/[0-9]{3}[A-Za-z]{3}
                if not re.fullmatch(r"[0-9]{15}", theCat.identif) and not re.fullmatch(r"([A-Z]{3}[0-9]{3}|[0-9]{3}[A-Z]{3})", theCat.identif):
                    message = [ [3, "Identification incorrecte (puce: 15 chiffres, tatouage: 3 chiffres+3 lettres ou l'inverse)!"] ]
                    theCat.regnum = 0
                    return render_template("cat_page.html", devsite=devel_site, user=current_user, cat=theCat, falist=User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).order_by(User.FAid).all(), msg=message,
                                       FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)

            # if for any reason the FA is invalid, then put it here
            if cmd != "adm_addcathere":
                FAid = int(request.form["FAid"]);
                # validate the id
                newFA = User.query.filter_by(id=FAid).first()
                faexists = newFA is not None;

                if cmd == "adm_addcatputFA" and faexists:
                    cat_associate_to_FA(theCat, newFA)

            else: # cmd == "adm_addcathere"
                cat_associate_to_FA(theCat, current_user)

            # problem: cat_associate_to_FA kills temp_owner.... so we reset it with the provided name if any
            if fatemp:
                # if adding to refuge, make sure it's a valid cage id
                # otherwise, update only if adding to FAtemp
                if (isRefuge(theCat.owner_id) and isValidCage(fatemp)) or isFATemp(theCat.owner_id):
                    theCat.temp_owner = fatemp

            db.session.add(theCat)
            # make sure we have an id
            db.session.commit()

            # generate the event
            session["pendingmessage"] = [ [0, "Chat {} rajouté dans le système".format(theCat.asText())] ]
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: rajoute dans le systeme".format(current_user.FAname))
            db.session.add(theEvent)

            current_user.FAlastop = datetime.now()
            db.session.commit()
            return redirect(url_for('fapage'))
        else:
            return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to add cat", FAids=FAidSpecial)

    # existing cat, populate the page with the available data
    theCat = Cat.query.filter_by(id=catid).first();
    if theCat == None:
        return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="invalid cat id", FAids=FAidSpecial)
#        return redirect(url_for('fapage'))

    # if we're working on another user's cats, show the information on top of the page
    FAid, theFA = getViewUser()

    if FAid == None:
        return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

    # determine if we can access the data
    catMode, vetMode, searchMode = accessPrivileges(theCat.owner)

    # if no access, no access....
    if catMode == ACC_NONE:
        return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="insufficient privileges to access cat data", FAids=FAidSpecial)

    # vet list will be needed
    VETlist = User.query.filter_by(FAisVET=True).order_by(User.FAname).all()

    if catMode == ACC_RO:
        # FAid != current_user.id is implied
        return render_template("cat_page.html", devsite=devel_site, user=current_user, otheruser=theFA, cat=theCat, readonly=True,
                               VETids=VETlist, VETdef=DEFAULT_VET, FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)

    # if we reach here, we have at least ACC_FULL
    # some operations may still be unavailable!

    FAlist = []
    if catMode == ACC_TOTAL:
        FAlist = User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).order_by(User.FAid).all()

    # handle generation of the page
    if cmd == "fa_viewcat":
        if "pendingmessage" in session:
            message = session["pendingmessage"]
            session.pop("pendingmessage")
        else:
            message = []

        return render_template("cat_page.html", devsite=devel_site, user=current_user, cat=theCat, msg=message,
                               falist=FAlist, VETids=VETlist, VETdef=DEFAULT_VET, FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)

    # cat commands, except for "cancel" we always process any data change
    if cmd == "fa_modcat" or cmd == "fa_modcatr" or cmd == "fa_adopted" or cmd == "fa_anonfa" or cmd == "fa_dead" or (cmd == "adm_putcat" and catMode == ACC_TOTAL):
        # return jsonify(request.form.to_dict())

        # update cat information and indicate what was changed
        # info is Adopt Name Ident Sex Birthdate L(hairlen) Color (c)omments Description Picture F(tempFA)/C(cage)
        updated = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        # NOTE: we use ident also to deal with registre, by setting it to "R"

        message = []

        # see if a temp cat was given a real regnum
        if theCat.regnum < 0 and "c_registre" in request.form and request.form["c_registre"] and catMode == ACC_TOTAL:
            # validate the regnum
            try:
                rr = request.form["c_registre"].split('-')
                rn = int(rr[0]) + 10000*int(rr[1])
            except:
                rn = -1

            if rn > 0:
                # ensure that registre is unique
                checkCat = Cat.query.filter_by(regnum=rn).first()

                if checkCat:
                    # this is bad, we regenerate the page wit the current data
                    message = [ [3, "Le numéro de registre existe déjà!"] ]
                    theCat.regnum = -1
                    return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, msg=message,
                                           VETids=VETlist, VETdef=DEFAULT_VET, FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)

                theCat.regnum = rn
                # we indicate this as a separate event
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: enregistre comme {}".format(current_user.FAname, request.form["c_registre"]))
                db.session.add(theEvent)
                updated[2] = 'R'
            else: # invalid regnum
                message = [ [3, "Numéro de registre non valable!"] ]
                return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, msg=message,
                                       VETids=VETlist, VETdef=DEFAULT_VET, FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)

        if theCat.name != request.form["c_name"]:
            theCat.name = request.form["c_name"]
            updated[1] = 'N'

        # only deal with this for FATEMP cats
        if isFATemp(theCat.owner_id):
            if theCat.temp_owner != request.form["c_fatemp"]:
                # we indicate this as a transfer
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré de [{}] a [{}]".format(current_user.FAname, theCat.temp_owner, request.form["c_fatemp"]))
                db.session.add(theEvent)
                theCat.temp_owner = request.form["c_fatemp"]
                updated[10] = 'F'

        # only update the cage for refuge cats
        if isRefuge(theCat.owner_id):
            if theCat.temp_owner != request.form["c_cage"]:
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: changé de cage de [{}] a [{}]".format(current_user.FAname, theCat.temp_owner, request.form["c_cage"]))
                db.session.add(theEvent)
                theCat.temp_owner = request.form["c_cage"]
                updated[10] = 'C'

        if theCat.sex != int(request.form["c_sex"]):
            theCat.sex=request.form["c_sex"]
            updated[3] = 'S'

        try:
            bd = datetime.strptime(request.form["c_birthdate"], "%Y-%m-%d")
        except ValueError:
            bd = None

        if theCat.birthdate != bd:
            theCat.birthdate = bd
            updated[4] = "B"

        if theCat.color != int(request.form["c_color"]):
            theCat.color = request.form["c_color"]
            updated[6] = 'C'

        if theCat.longhair != int(request.form["c_hlen"]):
            theCat.longhair = request.form["c_hlen"]
            updated[5] = 'L'

        if theCat.identif != request.form["c_identif"].upper():
            newid = request.form["c_identif"].upper()


            # validate the id
            if newid:
                # this must either be [0-9]{15} or [A-Za-z]{3}[0-9]{3}/[0-9]{3}[A-Za-z]{3}
                if not re.fullmatch(r"[0-9]{15}", newid) and not re.fullmatch(r"([A-Z]{3}[0-9]{3}|[0-9]{3}[A-Z]{3})", newid):
                    message.append([3, "Identification incorrecte (puce: 15 chiffres, tatouage: 3 chiffres+3 lettres ou l'inverse)!"])
                # data is not updated
                else:
                    theCat.identif = newid
                    updated[2] = 'I'

        if theCat.comments != request.form["c_comments"]:
            theCat.comments = request.form["c_comments"]
            updated[7] = 'c'

        if theCat.description != request.form["c_description"]:
            theCat.description = request.form["c_description"]
            updated[8] = 'D'

        if theCat.adoptable != (request.form["c_adoptable"] == "1"):
            theCat.adoptable = (request.form["c_adoptable"] == "1")
            updated[0] = 'A'

        if 'img_erase' in request.form:
            # delete the file (existing or not....)
            if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum))):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))
                updated[9] = 'P'
        else:
           if 'img_file' in request.files:
                img_file = request.files['img_file']

                if img_file:
                    filename = secure_filename(img_file.filename)
                    img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    # now rename the file and strip metadata (resize also???)
                    theImage = Image.open(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    theImage = ImageOps.exif_transpose(theImage)
                    theImage.save(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    updated[9] = 'P'

        # indicate moodification of the data
        updated = "".join(updated)

        if updated != "-----------":
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: mise à jour des informations {}".format(current_user.FAname, updated))
            db.session.add(theEvent)
            cat_updated = True
        else:
            cat_updated = False

        # handle the vet visits
        visitupdated = ""

        # iterate through all the planned visits and see if they have been updated....
        # extract all planned visits which are now executed
        modvisits = []
        for k in request.form.keys():
            if k.startswith("oldv_") and k.endswith("_state"): # and int(request.form[k]) != 1:
                modvisits.append(k)

        for mv in modvisits:
            # extract the visit id and information
            mvid = mv[5:-6]
            prefix = "oldv_"+mvid
            VisitType = vetMapToString(request.form, prefix)
            VisitVet = request.form[prefix+"_vet"]
            VisitDate = request.form[prefix+"_date"]
            VisitState = int(request.form[prefix+"_state"])
            VisitComments = request.form[prefix+"_comments"]

            # perform the update and any associated autoplan
            vres = cat_updateVetVisit(mvid, VETlist, theCat, VisitState, VisitType, VisitVet, VisitDate, VisitComments)

            if vres:
                if vres.startswith("visit"):
                    return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage=vres, FAids=FAidSpecial)
                else:
                    visitupdated += vres
                    cat_updated = True

        # end for mv in modvisits

        # new vetvisit, if defined: generate the vetinfo record and the associated event
        VisitType = vetMapToString(request.form, "visit")
        VisitVet = request.form["visit_vet"]
        VisitDate = request.form["visit_date"]
        VisitPlanned = (int(request.form["visit_state"]) == 1)
        VisitComments = request.form["visit_comments"]

        vres = cat_addVetVisit(VETlist, theCat, VisitPlanned, VisitType, VisitVet, VisitDate, VisitComments)

        if vres:
            if vres.startswith("visit"):
                # should we do an explicit rollback?
                return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage=vres, FAids=FAidSpecial)
            else:
                visitupdated += vres
                cat_updated = True

        if cat_updated or visitupdated:
            theCat.lastop = datetime.now()
            current_user.FAlastop = datetime.now()
            db.session.commit()
            message.append([0, "{}/{} informations mises á jour: {}{}".format(theCat.regStr(), theCat.name, updated, visitupdated)])
        else:
            message.append([0, "{}/{} aucune information était modifiée".format(theCat.regStr(), theCat.name)])

        # if we stay on the page, regenerate it directly
        if cmd == "fa_modcatr":
            session["pendingmessage"] = message
            return render_template("cat_page.html", devsite=devel_site, user=current_user, cat=theCat, falist=FAlist, msg=message,
                                   VETids=VETlist, VETdef=DEFAULT_VET, FAids=FAidSpecial, TabCols=DBTabColor, TabCages=TabCage)

        if cmd == "fa_modcat":
            session["pendingmessage"] = message
            return redirect(url_for('fapage'))

        if cmd == "fa_adopted":
            newFA = User.query.filter_by(id=FAidSpecial[0]).first()
            cat_associate_to_FA(theCat, newFA)

            # generate the event
            message.append([0, "Chat {} transféré dans les adoptés".format(theCat.asText())])
            session["pendingmessage"] = message
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: donné aux adoptants".format(current_user.FAname))
            db.session.add(theEvent)
            current_user.FAlastop = datetime.now()
            db.session.commit()
            return redirect(url_for('fapage'))

        if cmd == "fa_anonfa":
            # move to temp FA, we'll deal with this later
            newFA = User.query.filter_by(id=FAidSpecial[4]).first()
            cat_associate_to_FA(theCat, newFA)
            theCat.temp_owner = "FA INCONNUE"

            # generate the event
            message.append([0, "Chat {} transféré dans une FA non definie".format(theCat.asText())])
            session["pendingmessage"] = message
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transferé dans une FA non definie".format(current_user.FAname))
            db.session.add(theEvent)
            current_user.FAlastop = datetime.now()
            db.session.commit()
            return redirect(url_for('fapage'))

        if cmd == "fa_dead":
            newFA = User.query.filter_by(id=FAidSpecial[1]).first()
            cat_associate_to_FA(theCat, newFA)

            # generate the event
            message.append([0, "Chat {} transféré dans les décédés".format(theCat.asText())])
            session["pendingmessage"] = message
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: indiqué décédé".format(current_user.FAname))
            db.session.add(theEvent)
            current_user.FAlastop = datetime.now()
            db.session.commit()
            return redirect(url_for('fapage'))

        if cmd == "adm_putcat" and catMode == ACC_TOTAL:
            FAid = int(request.form["FAid"])
            # validate the id
            newFA = User.query.filter_by(id=FAid).first()

            if newFA and FAid != theCat.owner_id:
                # generate the event
                message.append([0, "Chat {} transféré chez {}".format(theCat.asText(), newFA.FAname)])
                session["pendingmessage"] = message
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré de {} a {}".format(current_user.FAname, theCat.owner.FAname, newFA.FAname))
                db.session.add(theEvent)
                # modify the FA
                cat_associate_to_FA(theCat, newFA)

                current_user.FAlastop = datetime.now()
                db.session.commit()

            return redirect(url_for('fapage'))

    # modify the cat's vet visits
    if cmd == "fa_modvet" and catMode >= ACC_FULL:
        # prepare the list of preexisting vet visits by subtracting all the executed from the cat's vetshort
        vshort = theCat.vetshort

        for vv in theCat.vetvisits:
            if not vv.planned:
                vshort = vetSubStrings(vshort, vv.vtype)

        return render_template("vet_page.html", devsite=devel_site, user=current_user, catVet=theCat,
                               prevtype=vshort, VETids=VETlist, VETdef=DEFAULT_VET, FAids=FAidSpecial, TabCols=DBTabColor)

    # this should never be reached
    return render_template("error_page.html", devsite=devel_site, user=current_user, errormessage="command error (/cat)", FAids=FAidSpecial)
