from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair
from app.permissions import UT_FA, UT_REFUGE, UT_FATEMP
from app.models import User, Cat
from flask import render_template, redirect, request, url_for, session, Response
from flask_login import login_required, current_user
from datetime import datetime


@app.route("/list", methods=["GET", "POST"])
@login_required
def listpage():
    if request.method == "GET":
        return redirect(url_for('fapage'))

    cmd = request.form["action"]

    if cmd == "sv_viewFA":
        # global list of the FAs

        # special FA we want some data from
        REFfa = User.query.filter_by(usertype=UT_REFUGE).first()
        TEMPfa = User.query.filter_by(usertype=UT_FATEMP).first()

        # get the correct list of FAs
        FAlist=User.query.filter_by(usertype=UT_FA).order_by(User.FAid).all()

        return render_template("list_page.html", devsite=devel_site, user=current_user, falist=FAlist, refugfa=REFfa, tempfa=TEMPfa)

    if cmd == "sv_viewFAresp" and current_user.hasReferent():
        # FA list for a referent (no specials)

        FAlist=User.query.filter_by(FAresp_id=current_user.id).order_by(User.FAid).all()

        return render_template("list_page.html", devsite=devel_site, user=current_user, rfalist=FAlist)

#    if cmd == "sv_viewFAresp" and (current_user.FAisRF):
        # special FA we want some data from
#        REFfa=User.query.filter_by(FAisREF=True).first()

        # all FAs we take care of (we assume they are FAs....)

#        return render_template("list_page.html", user=current_user, falist=FAlist, refugfa=REFfa, FAids=FAidSpecial)

    if current_user.hasSuperviseur() and cmd == "sv_globalTab":
        # list of all cats
        session["otherMode"] = "special-all"
        return redirect(url_for('fapage'))

    if current_user.hasSuperviseur() and cmd == "sv_adoptTab":
        # list of all cats with adoptable=true
        session["otherMode"] = "special-adopt"
        return redirect(url_for('fapage'))

    # default is indicate error
    return render_template("error_page.html", user=current_user, errormessage="command error (/list)")


def exportCSV(catlist):
    csv="FA,Registre,Puce,Nom,Sexe,Date Naissance,Couleur,Poil,Veterinaire,Adoptable,Commentaires\n"

    for cat in catlist:
        # historical cats are ignored ?
        #if cat.owner.FAisHIST:
        #    continue

        # this is looking for trouble.....
        cdesc = cat.comments
        cdesc.replace('"', '""')

        csv += ('"'+cat.nameFA()+'",'+cat.regStr()+','+cat.identif+',"'+cat.name+'",'+
            TabSex[cat.sex]+','+(cat.birthdate.strftime("%d/%m/%y") if cat.birthdate else '')+','+TabColor[cat.color]+','+
            TabHair[cat.longhair]+','+cat.vetshort+','+('Adoptable' if cat.adoptable else '')+',"'+cdesc+'"\n')

    return csv


@app.route("/listcsv")
@login_required
def listdownload():
    if current_user.hasSuperviseur():
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
    if current_user.hasSuperviseur():
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
