from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair, FAidSpecial
from app.models import User, Cat
from flask import render_template, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import and_


@app.route("/list", methods=["GET", "POST"])
@login_required
def listpage():
    if request.method == "GET":
        return redirect(url_for('fapage'))

    cmd = request.form["action"]

    if (cmd == "sv_viewFA" and (current_user.FAisADM or current_user.FAisOV)) or (cmd == "sv_viewFAresp" and (current_user.FAisRF)):
        # special FA we want some data from
        REFfa=User.query.filter_by(id=FAidSpecial[3]).first()
        TEMPfa=User.query.filter_by(id=FAidSpecial[4]).first()

        # prepare the table of the RFs
        RFlist=User.query.filter_by(FAisRF=True).all()

        RFtab = {}
        for rf in RFlist:
            RFtab[rf.id] = rf.FAname

        # get the correct list of FAs
        if cmd == "sv_viewFA":
            FAlist=User.query.filter(and_(User.FAisFA==True,User.id!=FAidSpecial[4])).order_by(User.FAid).all()
        else: # cmd == "sv_viewFAresp"
            FAlist=User.query.filter_by(FAresp_id=current_user.id).order_by(User.FAid).all()

        return render_template("list_page.html", devsite=devel_site, user=current_user, falist=FAlist, rftab=RFtab, refugfa=REFfa, tempfa=TEMPfa, FAids=FAidSpecial)

#    if cmd == "sv_viewFAresp" and (current_user.FAisRF):
        # special FA we want some data from
#        REFfa=User.query.filter_by(FAisREF=True).first()

        # all FAs we take care of (we assume they are FAs....)

#        return render_template("list_page.html", user=current_user, falist=FAlist, refugfa=REFfa, FAids=FAidSpecial)

    if cmd == "sv_globalTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats
        session["otherMode"] = "special-all"
        return redirect(url_for('fapage'))

    if cmd == "sv_adoptTab" and (current_user.FAisADM or current_user.FAisOV):
        # list of all cats with adoptable=true
        session["otherMode"] = "special-adopt"
        return redirect(url_for('fapage'))

    # default is indicate error
    return render_template("error_page.html", user=current_user, errormessage="command error (/list)", FAids=FAidSpecial)


def exportCSV(catlist):
    csv="FA,Registre,Puce,Nom,Sexe,Date Naissance,Couleur,Poil,Veterinaire,Adoptable,Commentaires\n"

    for cat in catlist:
        # historical cats are ignored ?
        #if cat.owner.FAisHIST:
        #    continue

        # this is looking for trouble.....
        cdesc = cat.comments
        cdesc.replace('"', '""')

        csv += ('"'+(cat.owner.FAname if cat.owner_id!=FAidSpecial[4] else ("["+cat.temp_owner+"]"))+'",'+cat.regStr()+','+cat.identif+',"'+cat.name+'",'+
            TabSex[cat.sex]+','+(cat.birthdate.strftime("%d/%m/%y") if cat.birthdate else '')+','+TabColor[cat.color]+','+
            TabHair[cat.longhair]+','+cat.vetshort+','+('Adoptable' if cat.adoptable else '')+',"'+cdesc+'"\n')

    return csv


@app.route("/listcsv")
@login_required
def listdownload():
    if current_user.FAisADM or current_user.FAisOV:
        # generate the global table as CSV file
        catlist=Cat.query.all()

        csv = exportCSV(catlist)

        current_user.FAlastop = datetime.now()
        db.session.commit()

        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=chatsFA.csv"})

    # default is return to index
    return redirect(url_for('fapage'))


@app.route("/listcsva")
@login_required
def listadownload():
    if current_user.FAisADM or current_user.FAisOV:
        # generate the table as CSV file
        catlist=Cat.query.filter_by(adoptable=True).all()

        csv = exportCSV(catlist)

        current_user.FAlastop = datetime.now()
        db.session.commit()

        return Response(
            csv,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=adoptables.csv"})

    # default is return to index
    return redirect(url_for('fapage'))
