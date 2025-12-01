from app import app, db, devel_site
from app.staticdata import DBTabColor, FAidSpecial
from app.helpers import ERAsum, cat_associate_to_FA
from app.models import User, Cat, Event
from flask import render_template, redirect, request, url_for
from flask_login import login_required, current_user
from datetime import datetime
from dateutil.relativedelta import relativedelta

# this page handles the requests for the menu "Operations Refuge"

# this is to allow "back" from genbonSter/SterMan
@app.route("/refbsc", methods=["GET"])
@login_required
def refugebscpage():
    if not current_user.FAisREF:
       return render_template("error_page.html", user=current_user, errormessage="acion only available for REF", FAids=FAidSpecial)

    # we rely on the webpage to do the job
    return render_template("refuge_page.html", devsite=devel_site, user=current_user, pagetype=2, FAids=FAidSpecial, TabCols=DBTabColor)

@app.route("/refpec", methods=["GET"])
@login_required
def refugepecpage():
    if not current_user.FAisREF:
       return render_template("error_page.html", user=current_user, errormessage="acion only available for REF", FAids=FAidSpecial)

    # we rely on the webpage to do the job
    return render_template("refuge_page.html", devsite=devel_site, user=current_user, pagetype=1, FAids=FAidSpecial, TabCols=DBTabColor)

@app.route("/refuge", methods=["GET", "POST"])
@login_required
def refugepage():
    if request.method == "GET":
        return redirect(url_for('fapage'))

    # refuge actions can only be done by refuge
    if not current_user.FAisREF:
       return render_template("error_page.html", user=current_user, errormessage="acion only available for REF", FAids=FAidSpecial)

    cmd = request.form["action"]

    # prise en charge - generate the document
    if cmd == "ref_genprise" or cmd == "ref_genprisesave":
        messages = []

        # get the data
        ptype = 1 if request.form["pec_type"] == 'T' else 2

        try:
            date = datetime.strptime(request.form["pec_date"], "%Y-%m-%d")
        except ValueError:
            date = datetime.now()

        motif = request.form["pec_why"]
        amdata = [request.form[k] for k in ('pec_nom', 'pec_prenom', 'pec_adresse', 'pec_cp', 'pec_ville', 'pec_tel', 'pec_email')]

        cats = []
        for i in range(1,7):
            # only fill the lines where we have a name
            # note: we add two extra numeric columns with the sex and color representation (useful when adding a cat)
            cn = request.form["pec_name{}".format(i)]

            if cn:
                cs = request.form["pec_sex{}".format(i)]
                csn = (1 if cs == 'F' else (2 if cs == 'M' else 0))
                ccn = int(request.form["pec_color{}".format(i)])
                cc = DBTabColor[ccn]
                ca = request.form["pec_age{}".format(i)]
                cats.append([cn, cs, cc, ca, request.form["pec_id{}".format(i)], request.form["pec_spec{}".format(i)], csn, ccn])
            else:
                cats.append(['', '', '', '', '', '', 0, 0])

        carnet = 1 if 'pec_carnet' in request.form else 0
        icad = 1 if 'pec_icad' in request.form else 0
        vet = [request.form[k] for k in ('pec_vetv', 'pec_vett', 'pec_vets')]

        # note that in reality we ignore the radio selection, unless everything is empty
        locref = request.form['pec_refwhere']
        locFA = request.form['pec_fawhere']

        if locFA.lower() == "amenant":
            locFA = amdata[0] + " " + amdata[1]

        if not locref and not locFA:
            if request.form["pec_where"] == "R":
                locref = '...au refuge...'
            else:
                locFA = '...une FA...'

        # if we have to add the cats, do it and prepare the messages
        if cmd == "ref_genprisesave":
            # use the cat information to add the cats
            # decide where they go: note that while it may be possible to fill both refuge and FA
            # the program cannot guess, so they all go to refuge if it's not empty
            if locref:
                theFA = User.query.filter_by(id=FAidSpecial[3]).first()
                fatemp = "AXX"
            else:
                # we could try an exact match, for now just use TempFA
                theFA = User.query.filter_by(id=FAidSpecial[4]).first()
                fatemp = locFA

            for cd in cats:
                # empty name = ignore
                if not cd[0]:
                    continue

                # create the cat
                # for vetshort, try to guess something from the data
                # this may fail horribly for a mother+litter, but that's life
                vetstr = ('-' +
                    ('1' if carnet and vet[0] else '-') +
                    '-' +
                    ('P' if cd[4] else '-') +
                    ('T' if carnet and vet[1] else '-') +
                    ('S' if vet[2] else '-') +
                    '--')

                # save what we can in the comment string
                commstr = "PeC {}: amenant {} {}, {}".format(date.strftime("%d/%m/%y"), amdata[0], amdata[1], motif)

                theCat = Cat(regnum=-1, temp_owner=fatemp, name=cd[0], sex=cd[6], color=cd[7], longhair=0, identif=cd[4],
                    vetshort=vetstr, comments=commstr, description='', adoptable=False)
                cat_associate_to_FA(theCat, theFA)

                db.session.add(theCat)
                # make sure we have an id
                db.session.commit()

                # generate the event
                messages.append("Chat N{}/{} rajoute dans le systeme".format(theCat.id, cd[0]))
                theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: auto-genere par prise en charge".format(current_user.FAname))
                db.session.add(theEvent)

            db.session.commit()

        pdfname = "PeC-{} {}-{}".format(amdata[0], amdata[1], date.strftime("%Y-%m-%d"))
        return render_template("pecform_page.html", user=current_user, msg=messages, pectitle=pdfname, pec_type=ptype, pec_date=date, pec_motif=motif, amenant=amdata, peccats=cats, pec_carnet=carnet, pec_icad=icad, pec_vet=vet, pec_refuge=locref, pec_FA=locFA)

    # bon sterilisation for an adopted cat - called by the /refbsc page
    if cmd == "ref_genbonSter" or cmd == "ref_genbonSterMan":
        # if we have the string from refugilys, we need nothing else
        if cmd == "ref_genbonSter":
            data = request.form["bcs_data"]
            vals = data.split(";")

            # data must start with AD_BCS
            if vals[0] != "AD_BSC" or len(vals) != 11:
                message = [ [3, "Donnees non valables! {}/11".format(len(vals))] ]
                return render_template("refuge_page.html", devsite=devel_site, user=current_user, msg=message, pagetype=2, FAids=FAidSpecial, TabCols=DBTabColor)

            prop = vals[10].split("/")
            if len(prop) < 7:
                message = [ [3, "Donnees proprietaire non valables! {}/7".format(len(prop))] ]
                return render_template("refuge_page.html", devsite=devel_site, user=current_user, msg=message, pagetype=2, FAids=FAidSpecial, TabCols=DBTabColor)

        else:
            # python is just complete shit
            vals = ["", "", "", "", "", "", "", "", "", "", ""]
            prop = ["", "", "", "", "", "", ""]
            # extract the data from the form, simulating the string from refugilys
            #vals[0] = "AD_BSC"
            vals[1] = request.form["bcs_regnum"]
            vals[2] = request.form["bcs_name"].upper()
            vals[3] = request.form["bcs_race"].upper()
            vals[4] = request.form["bcs_sex"][:1]
            vals[5] = DBTabColor[int(request.form["bcs_color"])]
            vals[6] = request.form["bcs_hlen"][:1]
            vals[7] = request.form["bcs_bdate"]
            vals[8] = request.form["bcs_id"]
            vals[9] = request.form["bcs_addate"]
            # vals[10] provided already split
            prop[0] = request.form["bcs_adnp"].upper()
            prop[1] = request.form["bcs_adad"]
            prop[2] = ""
            prop[3] = ""
            prop[4] = request.form["bcs_adcp"] + " " + request.form["bcs_adcy"].upper()
            prop[5] = request.form["bcs_adtel"]
            prop[6] = ""

        # check that puce is defined...
        if not vals[8]:
            message = [ [3, "Identification du chat non indiquee!"] ]
            return render_template("refuge_page.html", devsite=devel_site, user=current_user, msg=message, pagetype=2, FAids=FAidSpecial)

        # adapt according to sex
        if vals[4] == "F":
            optype = "stérilisation"
            opcost = "70 euros"
        elif vals[4] == "M":
            optype = "castration"
            opcost = "36 euros"
        else:
            message = [ [3, "Sexe du chat non indique!"] ]
            return render_template("refuge_page.html", devsite=devel_site, user=current_user, msg=message, pagetype=2, FAids=FAidSpecial)

        # generate the dates
        try:
            bdate = datetime.strptime(vals[7], "%d/%m/%y")
        except ValueError:
            message = [ [3, "Date de naissance non valable!"] ]
            return render_template("refuge_page.html", devsite=devel_site, user=current_user, msg=message, pagetype=2, FAids=FAidSpecial)

        # steril is +6m, lim is steril +2m
        datpro = bdate+relativedelta(months=6)
        #datlim = datpro.replace(day=1)
        datlim = datpro+relativedelta(months=2)
        #datlim = datlim+relativedelta(days=-1)

        datpro = datpro.strftime("%d/%m/%y")
        datlim = datlim.strftime("%d/%m/%y")

        # header datlim regnum puce bdate sex propname addate
        data = "ERA;AD_BSC;" + datlim + ";" + vals[1] + ";" + vals[8] + ";" + vals[7] + ";" + vals[4] + ";" + prop[0] + ";" + vals[9] + ";"
        qrstr = data + ERAsum(data)

        pdfname = "bon-steril-{}".format(prop[0])
        return render_template("bonsteril_page.html", user=current_user, bvtitle=pdfname, opupper=optype.upper(), qrdata=qrstr, propr=prop,
                                    datcont=vals[9], nom=vals[2], race=vals[3], sexe=vals[4], couleur=vals[5], hlen=vals[6],
                                    datnaiss=vals[7], regnum=vals[1], puce=vals[8],
                                    dprov=datpro, dlimit=datlim, optype=optype, opcost=opcost)

    return render_template("error_page.html", user=current_user, errormessage="command error (/refuge)", FAids=FAidSpecial)
