from app import app, db
from app.staticdata import FAidSpecial, ACC_NONE, ACC_RO, ACC_FULL, ACC_TOTAL
from app.models import User, Cat, VetInfo, Event
from app.helpers import vetMapToString, vetAddStrings
from flask import render_template, redirect, request, url_for, session
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from datetime import datetime
import os
from PIL import Image
from werkzeug.utils import secure_filename


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

    # generate an empty page to add a new cat
    if cmd == "adm_newcat" and current_user.FAisADM:
        theCat = Cat(regnum=0)
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).all(), FAids=FAidSpecial)

    if (cmd == "adm_addcathere" or cmd == "adm_addcatputFA") and current_user.FAisADM:
        # generate the new cat using the form information
        vetstr = vetMapToString(request.form, "visit")

        try:
            bdate = datetime.strptime(request.form["c_birthdate"], "%d/%m/%y")
        except ValueError:
            bdate = None

        # convert registre
        rr = request.form["c_registre"].split('-')
        rn = int(rr[0]) + 10000*int(rr[1])

        theCat = Cat(regnum=rn, temp_owner=request.form["c_fatemp"], name=request.form["c_name"], sex=request.form["c_sex"], birthdate=bdate,
                    color=request.form["c_color"], longhair=request.form["c_hlen"], identif=request.form["c_identif"],
                    description=request.form["c_description"], comments=request.form["c_comments"], vetshort=vetstr,
                    adoptable=(request.form["c_adoptable"]=="1"))

        # ensure that registre is unique
        checkCat = Cat.query.filter_by(regnum=rn).first()

        if checkCat:
            # this is bad, we regenerate the page wit the current data
            message = [ [3, "Le numéro de registre existe déjà!"] ]
            theCat.regnum = 0
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).all(), msg=message, FAids=FAidSpecial)

        # if for any reason the FA is invalid, then put it here
        if cmd != "adm_addcathere":
            FAid = int(request.form["FAid"]);
            # validate the id
            newFA = User.query.filter_by(id=FAid).first()
            faexists = newFA is not None;

            if cmd == "adm_addcatputFA" and faexists:
                newFA.numcats += 1
                theCat.owner_id = FAid
            else:
                current_user.numcats += 1
                theCat.owner_id = current_user.id

        else: # cmd == "addcathere"
            current_user.numcats += 1
            theCat.owner_id = current_user.id

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

    # existing cat, populate the page with the available data
    theCat = Cat.query.filter_by(id=catid).first();
    if theCat == None:
        return render_template("error_page.html", user=current_user, errormessage="invalid cat id", FAids=FAidSpecial)
#        return redirect(url_for('fapage'))

    # if we're working on another user's cats, show the information on top of the page
    FAid = current_user.id
    access = ACC_NONE

    if "otherFA" in session:
        FAid = session["otherFA"]
        theFA = User.query.filter_by(id=FAid).first()
        faexists = theFA is not None;

        if not faexists:
            return render_template("error_page.html", user=current_user, errormessage="invalid FA id", FAids=FAidSpecial)

    # upgrade access depending on our status
    # OV can see anything in RO mode
    if current_user.FAisOV:
        access = ACC_RO

    # we can always see our cats, and ADM can always see all
    if current_user.FAisFA and theCat.owner_id == current_user.id:
        access = ACC_FULL

    # we also have full access to any cat a FA we resp
    if theCat.owner.FAresp_id == current_user.id:
        access = ACC_FULL

    if current_user.FAisADM:
        access = ACC_TOTAL

    # if no access, no access....
    if access == ACC_NONE:
        return render_template("error_page.html", user=current_user, errormessage="insufficient privileges to access cat data", FAids=FAidSpecial)

    # vet list will be needed
    VETlist = User.query.filter_by(FAisVET=True).all()

    if access == ACC_RO:
        # FAid != current_user.id is implied
        return render_template("cat_page.html", user=current_user, otheruser=theFA, cat=theCat, readonly=True, VETids=VETlist, FAids=FAidSpecial)

    # if we reach here, we have at least ACC_FULL
    # some operations may still be unavailable!

    FAlist = []
    if access == ACC_TOTAL:
        FAlist = User.query.filter(or_(User.FAisFA==True,User.FAisREF==True)).order_by(User.FAid).all()

    # handle generation of the page
    if cmd == "fa_viewcat":
        return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, VETids=VETlist, FAids=FAidSpecial)

    # cat commands
    if cmd == "fa_modcat" or cmd == "fa_modcatr":
        # return jsonify(request.form.to_dict())

        # update cat information and indicate what was changed
        # info is Adoppt Name Ident Sex Birthdate L(hairlen) Color (c)omments Description Picture
        updated = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        if theCat.name != request.form["c_name"]:
            theCat.name = request.form["c_name"]
            updated[1] = 'N'

        # only deal with this for FATEMP cats
        if theCat.owner_id == FAidSpecial[4]:
            if theCat.temp_owner != request.form["c_fatemp"]:
                # we indicate this as a transfer
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré de [{}] a [{}]".format(current_user.FAname, theCat.temp_owner, request.form["c_fatemp"]))
                db.session.add(theEvent)
                theCat.temp_owner = request.form["c_fatemp"]

        if theCat.sex != int(request.form["c_sex"]):
            theCat.sex=request.form["c_sex"]
            updated[3] = 'S'

        try:
            bd = datetime.strptime(request.form["c_birthdate"], "%d/%m/%y")
        except ValueError:
            bd = None

        if theCat.birthdate != bd:
            theCat.birthdate = bd
            updated[4] = "B"

        if theCat.color != int(request.form["c_color"]):
            theCat.color=request.form["c_color"]
            updated[6] = 'C'

        if theCat.longhair != int(request.form["c_hlen"]):
            theCat.longhair=request.form["c_hlen"]
            updated[5] = 'L'

        if theCat.identif != request.form["c_identif"]:
            theCat.identif=request.form["c_identif"]
            updated[2] = 'I'

        if theCat.comments != request.form["c_comments"]:
            theCat.comments=request.form["c_comments"]
            updated[7] = 'c'

        if theCat.description != request.form["c_description"]:
            theCat.description=request.form["c_description"]
            updated[8] = 'D'

        if theCat.adoptable != (request.form["c_adoptable"] == "1"):
            theCat.adoptable=(request.form["c_adoptable"] == "1")
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
                    theImage.save(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    updated[9] = 'P'

        # indicate moodification of the data
        updated = "".join(updated)

        if updated != "----------":
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: mise à jour des informations {}".format(current_user.FAname, updated))
            db.session.add(theEvent)
            cat_updated = True
        else:
            cat_updated = False

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
                theCat.vetshort = vetAddStrings(theCat.vetshort, VisitType)
                et = "effectuee le"
                cat_updated = True
            else:
                et = "planifiee pour le"

            theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vetId, vtype=VisitType, vdate=VisitDate,
                planned=VisitPlanned, comments=request.form["visit_comments"])
            db.session.add(theVisit)
            db.session.commit()  # needed for vet.FAname

            # add it as event (planned or not)
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, VisitType, et, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
            db.session.add(theEvent)

        # iterate through all the planned visits and see if they have been updated....
        # extract all planned visits which are now executed
        modvisits = []
        for k in request.form.keys():
            if k.startswith("oldv_") and k.endswith("_state"): # and int(request.form[k]) != 1:
                modvisits.append(k)

        for mv in modvisits:
            # extract and validate the id
            mvid = mv[5:-6]

            theVisit = VetInfo.query.filter_by(id=mvid).first();
            if not theVisit:
                return render_template("error_page.html", user=current_user, errormessage="planned visit not found (invalid id)", FAids=FAidSpecial)

            # make sure it's related to this cat
            if theVisit.cat_id != theCat.id:
                return render_template("error_page.html", user=current_user, errormessage="visit/cat id mismatch", FAids=FAidSpecial)

            # generate the form name prefix
            prefix = "oldv_"+mvid
            vv_updated = False

            # if deleted, delete immediately
            if int(request.form[prefix+"_state"]) == 2:
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} annullée".format(current_user.FAname, theVisit.vtype))
                db.session.add(theEvent)
                db.session.delete(theVisit)
                continue

            # modify the visit with the new data (we'll need to get all of it....)
            # if all reasons have been removed, erase it
            VisitType = vetMapToString(request.form, prefix)

            if VisitType == "--------":
                # all reasons removed, erase this
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} annullée".format(current_user.FAname, theVisit.vtype))
                db.session.add(theEvent)
                db.session.delete(theVisit)
                continue

            # update the record
            if theVisit.vtype != VisitType:
                theVisit.vtype = VisitType
                vv_updated = True

            try:
                VisitDate = datetime.strptime(request.form[prefix+"_date"], "%d/%m/%y")
            except ValueError:
                VisitDate = datetime.now()

            if theVisit.vdate != VisitDate:
                theVisit.vdate = VisitDate
                vv_updated = True

            # validate the vet
            vet = next((x for x in VETlist if x.id==int(request.form[prefix+"_vet"])), None)

            if not vet:
                return render_template("error_page.html", user=current_user, errormessage="vet id is invalid", FAids=FAidSpecial)
            else:
                if theVisit.vet_id != vet.id:
                    theVisit.vet_id = vet.id
                    vv_updated = True

            if theVisit.comments != request.form[prefix+"_comments"]:
                theVisit.comments = request.form[prefix+"_comments"]
                vv_updated = True

            if int(request.form[prefix+"_state"]) != 1:
                # means it's not planned anymore
                theCat.vetshort = vetAddStrings(theCat.vetshort, VisitType)
                theVisit.planned = False
                cat_updated = True
                vv_updated = True
                et = "effectuee le"
            else:
                et = "re-planifiee pour le"

            if vv_updated:
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, VisitType, et, VisitDate.strftime("%d/%m/%y"), theVisit.vet.FAname))
                db.session.add(theEvent)

        # end for mv in modvisits

        if cat_updated:
            theCat.lastop = datetime.now()
        current_user.FAlastop = datetime.now()
        db.session.commit()
        message = [ [0, "Informations mises a jour"] ]

        # if we stay on the page, regenerate it directly
        if cmd == "fa_modcatr":
            return render_template("cat_page.html", user=current_user, cat=theCat, falist=FAlist, msg=message, VETids=VETlist, FAids=FAidSpecial)

        session["pendingmessage"] = message
        return redirect(url_for('fapage'))

    if cmd == "fa_adopted":
        newFA = User.query.filter_by(id=FAidSpecial[0]).first()
        newFA.numcats += 1
        theCat.owner.numcats -= 1
        theCat.owner_id = newFA.id
        theCat.adoptable = False
        # erase any planned visit
        VetInfo.query.filter_by(cat_id=theCat.id, planned=True).delete()
        theCat.lastop = datetime.now()
        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} transféré dans les adoptés".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: donné aux adoptants".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('fapage'))

    if cmd == "fa_dead":
        newFA = User.query.filter_by(id=FAidSpecial[1]).first()
        newFA.numcats += 1
        theCat.owner.numcats -= 1
        theCat.owner_id = newFA.id
        theCat.adoptable = False
        # erase any planned visit
        VetInfo.query.filter_by(cat_id=theCat.id, planned=True).delete()
        theCat.lastop = datetime.now()
        # generate the event
        session["pendingmessage"] = [ [0, "Chat {} transféré dans les décédés".format(theCat.asText())] ]
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: indiqué décédé".format(current_user.FAname))
        db.session.add(theEvent)
        current_user.FAlastop = datetime.now()
        db.session.commit()
        return redirect(url_for('fapage'))

    if cmd == "adm_putcat" and access == ACC_TOTAL:
        # cat information is not updated
        FAid = int(request.form["FAid"])
        # validate the id
        theFA = User.query.filter_by(id=FAid).first()

        if theFA and FAid != theCat.owner_id:
            # generate the event
            session["pendingmessage"] = [ [0, "Chat {} transféré chez {}".format(theCat.asText(), theFA.FAname)] ]
            theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: transféré de {} a {}".format(current_user.FAname, theCat.owner.FAname, theFA.FAname))
            db.session.add(theEvent)
            # modify the FA
            theFA.numcats += 1
            theCat.owner.numcats -= 1
            theCat.owner_id = FAid
            theCat.lastop = datetime.now()
            # in order to make it easier to list the "planned visits", any visit which is PLANNED is transferred to the new owner
            # the idea is than that any VetInfo with planned=True and doneby_id matching the user ALWAYS corresponds to cats he owns
            # this doesn't affect the visits which were performed. and the events will reflect the reality of who planned the visit since they are static
            theVisits = VetInfo.query.filter(and_(VetInfo.cat_id == theCat.id, VetInfo.planned == True)).all()
            for v in theVisits:
                v.doneby_id = FAid

            current_user.FAlastop = datetime.now()
            db.session.commit()

        return redirect(url_for('fapage'))

    # this should never be reached
    # display info about a cat
#    return render_template("cat_page.html", user=current_user, cat=theCat, falist=User.query.filter_by(FAisFA=True).all())
    return render_template("error_page.html", user=current_user, errormessage="command error (/cat)", FAids=FAidSpecial)
