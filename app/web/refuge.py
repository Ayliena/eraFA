from app import app, devel_site
from app.staticdata import DBTabColor, FAidSpecial
from app.helpers import ERAsum
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

@app.route("/refuge", methods=["GET", "POST"])
@login_required
def refugepage():
    if request.method == "GET":
        return redirect(url_for('fapage'))

    # refuge actions can only be done by refuge
    if not current_user.FAisREF:
       return render_template("error_page.html", user=current_user, errormessage="acion only available for REF", FAids=FAidSpecial)

    cmd = request.form["action"]

    # prise en charge - request for parameters
    if cmd == "ref_prise":
       return render_template("refuge_page.html", devsite=devel_site, user=current_user, pagetype=1, FAids=FAidSpecial, TabCols=DBTabColor)

    # prise en charge - generate the document
    if cmd == "ref_genprise":
       return render_template("error_page.html", user=current_user, errormessage="unimplemented ref_genprise", FAids=FAidSpecial)

    # bon sterilisation for an adopted cat - try to take the data from the clipboard, otherwise ask
#    if cmd == "ref_bonSter":
#        # we rely on the webpage to do the job
#        return render_template("refuge_page.html", devsite=devel_site, user=current_user, pagetype=2, FAids=FAidSpecial, TabCols=DBTabColor)

    # bon sterilisation for an adopted cat - called by the previous page
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
            if len(prop) != 7:
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
        bdate = datetime.strptime(vals[7], "%d/%m/%y")
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
        return render_template("bonsteril_page.html", user=current_user, opupper=optype.upper(), qrdata=qrstr, propr=prop,
                                    datcont=vals[9], nom=vals[2], race=vals[3], sexe=vals[4], couleur=vals[5], hlen=vals[6],
                                    datnaiss=vals[7], regnum=vals[1], puce=vals[8],
                                    dprov=datpro, dlimit=datlim, optype=optype, opcost=opcost)

    return render_template("error_page.html", user=current_user, errormessage="command error (/refuge)", FAids=FAidSpecial)
