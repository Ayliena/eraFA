from app import app, db
from app.models import User, Event, VetInfo
from app.staticdata import FAidSpecial, TabCage, ACC_NONE, ACC_RO, ACC_MOD, ACC_FULL, ACC_TOTAL, NO_VISIT
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from flask import session
from flask_login import current_user
import hashlib
import base64
import os
import re

# --------------- HELPER FUNCTIONS

def decodeRegnum(regnum):
    # decode a nnn-yy string and convert it to a number
    # returns -1 if the string is invalid
    if regnum.find('-') == -1:
        return -1

    rr = regnum.split('-')
    if len(rr) != 2 or not rr[0] or not rr[1]:
        return -1

    return int(rr[0]) + 10000*int(rr[1])


def encodeRegnum(regnum):
    if regnum > 0:
        return "{}-{}".format(regnum%10000, int(regnum/10000))
    else:
        return None

def isAdoptes(faid):
    return (faid == FAidSpecial[0])

def isDecedes(faid):
    return (faid == FAidSpecial[1])

def isHistorique(faid):
    return (faid == FAidSpecial[2])

def isRefuge(faid):
    return (faid == FAidSpecial[3])

def isFATemp(faid):
    return (faid == FAidSpecial[4])


def vetMapToString(vetmap, prefix):
    str =["-", "-", "-", "-", "-", "-", "-", "-"]
    if prefix+"_pv" in vetmap:
        str[0] = 'V'
    if prefix+"_r1" in vetmap:
        str[1] = '1'
    if prefix+"_rr" in vetmap:
        str[2] = 'R'
    if prefix+"_id" in vetmap:
        str[3] = 'P'
    if prefix+"_tf" in vetmap:
        str[4] = 'T'
    if prefix+"_sc" in vetmap:
        str[5] = 'S'
    if prefix+"_gen" in vetmap:
        str[6] = 'X'
    if prefix+"_ap" in vetmap:
        str[7] = 'D'
    return "".join(str)

def vetIsPrimo(vetstr):
    return (vetstr[0] == 'V')

def vetIsRappel1(vetstr):
    return (vetstr[1] == '1')

def vetIsRappelAnn(vetstr):
    return (vetstr[2] == 'R')

def vetIsIdent(vetstr):
    return (vetstr[3] == 'P')

def vetIsTest(vetstr):
    return (vetstr[4] == 'T')

def vetIsSteril(vetstr):
    return (vetstr[5] == 'S')

def vetIsSoins(vetstr):
    return (vetstr[6] == 'X')

def vetIsDepara(vetstr):
    return (vetstr[7] == 'D')

def vetStringToMap(vetstr, prefix):
    vmap = {}
    vmap[prefix+"_pv"] = (str[0] == 'V')
    vmap[prefix+"_r1"] = (str[1] == '1')
    vmap[prefix+"_rr"] = (str[2] == 'R')
    vmap[prefix+"_id"] = (str[3] == 'P')
    vmap[prefix+"_tf"] = (str[4] == 'T')
    vmap[prefix+"_sc"] = (str[5] == 'S')
    vmap[prefix+"_gen"] = (str[6] == 'X')
    vmap[prefix+"_ap"] = (str[7] == 'D')
    return vmap

def vetAddStrings(vetstr1, vetstr2):
    str = list(vetstr1)
    for i in range(0,8):
        if str[i] == '-':
            str[i] = vetstr2[i]

    return "".join(str)

def ERAsum(str1):
    m = hashlib.md5()
    m.update((str1 + '0C1s5qzQo5').encode('utf-8'))
    str2 = base64.b64encode(m.digest()).decode('utf-8')

    return str2[0:12]

def cat_associate_to_FA(theCat, newFA):
    if theCat.owner:
        theCat.owner.numcats -= 1

    theCat.owner_id = newFA.id
    newFA.numcats += 1

    # handle special cases, for FA use name (search) for refuge use cage id
    # for the special FAtemp, don't touch the information (which should have been set by the caller)
    if isRefuge(newFA.id):
        theCat.temp_owner = TabCage[0][0]
    elif isFATemp(newFA.id):
        theCat.temp_owner = "FA INCONNUE"
    else:
        theCat.temp_owner = newFA.FAname

    if isDecedes(newFA.id) or isAdoptes(newFA.id):
        theCat.adoptable = False
        # erase any planned visit
        VetInfo.query.filter_by(cat_id=theCat.id, planned=True).delete()
    else:
        # in order to make it easier to list the "planned visits", any visit which is PLANNED is transferred to the new owner
        # the idea is than that any VetInfo with planned=True and doneby_id matching the user ALWAYS corresponds to cats he owns
        # any validated visit is also reversed back to NON-validated
        # this doesn't affect the visits which were performed. and the events will reflect the reality of who planned the visit since they are static
        theVisits = VetInfo.query.filter(and_(VetInfo.cat_id == theCat.id, VetInfo.planned == True)).all()
        for v in theVisits:
            v.doneby_id = newFA.id
            v.validby_id = None

    theCat.lastop = datetime.now()
    return

def cat_delete(theCat):
    # start by erasing the image (if any)
    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum))):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))

    theCat.owner.numcats -= 1
    Event.query.filter_by(cat_id=theCat.id).delete()
    VetInfo.query.filter_by(cat_id=theCat.id).delete()
    db.session.delete(theCat)
    # note that WE DO NOT COMMIT

def cat_addVetVisit(VETlist, theCat, vplan, vtype, vvet, vdate, vcomm):
    # do we actually have anything to add?
    if vtype == NO_VISIT:
        return

    # validate the vet id
    vet = next((x for x in VETlist if x.id==int(vvet)), None)

    if not vet:
        return "visit: invalid vet id {}".format(vvet)

    # validate the date (empty = today)
    try:
        vdate = datetime.strptime(vdate, "%d/%m/%y")
    except ValueError:
        vdate = datetime.now()

    # generate the record and the event
    theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vet.id, vtype=vtype, vdate=vdate,
        planned=vplan, comments=vcomm)
    db.session.add(theVisit)
    db.session.commit()  # needed for vet.FAname

    # assume no additional return results
    vres = ""

    # if executed, then cumulate with the global and auto-plan next visit if needed
    if vplan:
        et = "planifiée pour le"
        # default state = not authorized
        theVisit.requested = False
        theVisit.transferred = False
        theVisit.validby_id = None

    else:
        et = "effectuée le"
        theCat.vetshort = vetAddStrings(theCat.vetshort, vtype)

        vres = cat_autoplanVisit(theCat, theVisit)

    # add it as event (planned or not)
    theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, vtype, et, vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
    db.session.add(theEvent)
    # note that WE DO NOT COMMIT

    return " +{}[{}]".format('P' if vplan else 'E', vtype) + vres


def cat_updateVetVisit(vvid, VETlist, theCat, vstate, vtype, vvet, vdate, vcomm):
    # get the visit we're supposed to update
    theVisit = VetInfo.query.filter_by(id=vvid).first();
    if not theVisit:
        return "visit: invalid visit id"

    # make sure it's related to this cat
    if theVisit.cat_id != theCat.id:
        return "visit: wrong cat id"

    # perform a paranoia check, but the visit passed should always be of type planned
    if not theVisit.planned:
        return "visit: attempt to update an executed visit"

    # vstate: 0=executed, 1=planned, 2=deleted

    # if deleted or all reasons are unchecked, remove it and forget about the rest
    if vstate == 2 or vtype == NO_VISIT:
        theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} annullée".format(current_user.FAname, theVisit.vtype))
        db.session.add(theEvent)
        db.session.delete(theVisit)
        return " -{}[{}]".format('P' if theVisit.planned else 'E', theVisit.vtype)

    vv_updated = False

    # update the record
    if theVisit.vtype != vtype:
        theVisit.vtype = vtype
        vv_updated = True

    try:
        vdate = datetime.strptime(vdate, "%d/%m/%y")
    except ValueError:
        vdate = datetime.now()

    if theVisit.vdate != vdate:
        theVisit.vdate = vdate
        vv_updated = True

    # validate the vet
    vet = next((x for x in VETlist if x.id==int(vvet)), None)

    if not vet:
        return "visit: invalid vet id"
    else:
        if theVisit.vet_id != vet.id:
            theVisit.vet_id = vet.id
            vv_updated = True

    if theVisit.comments != vcomm:
        theVisit.comments = vcomm
        vv_updated = True

    # assume no additional return results
    vres = ""

    if vstate != 1:
        # means it's not planned anymore -> executed
        et = "effectuee le"
        theCat.vetshort = vetAddStrings(theCat.vetshort, vtype)
        theVisit.planned = False

        # check for autoplan
        vres = cat_autoplanVisit(theCat, theVisit)

    else:
        et = "re-planifiee pour le"

        if vv_updated:
            # some parameters where changed, revoke authorization
            theVisit.requested = False
            theVisit.transferred = False
            theVisit.validby_id = None
        else:
            # no change was made at all, do and return nothing
            return ""

    # generate the event and return the information
    theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, vtype, et, vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
    db.session.add(theEvent)

    return " *{}[{}]".format('P' if theVisit.planned else 'E', vtype) + vres


def cat_executeVetVisit(vvid, theCat, vdate):
    # this is a simplified version of updateVetVisit which only changes the state and (maybe) date if provided

    # get the visit we're supposed to update
    theVisit = VetInfo.query.filter_by(id=vvid).first();
    if not theVisit:
        return "visit: invalid visit id"

    # make sure it's related to this cat
    if theVisit.cat_id != theCat.id:
        return "visit: wrong cat id"

    # perform a paranoia check, but the visit passed should always be of type planned
    if not theVisit.planned:
        return "visit: attempt to execute an executed visit"

    # only update the date if requested
    if vdate:
        try:
            vdate = datetime.strptime(vdate, "%d/%m/%y")
        except ValueError:
            vdate = datetime.now()

        theVisit.vdate = vdate

    # execute the visit
    et = "effectuee le"
    theCat.vetshort = vetAddStrings(theCat.vetshort, theVisit.vtype)
    theVisit.planned = False

    # check for autoplan
    vres = cat_autoplanVisit(theCat, theVisit)

    # generate the event and return the information
    theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, theVisit.vtype, et, theVisit.vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
    db.session.add(theEvent)

    return " *E[{}]".format(theVisit.vtype) + vres


# after recording an executed visit, see if we should auto-plan the next
def cat_autoplanVisit(theCat, vvisit):
    # paranoia check
    if vvisit.planned:
        return ""

    # prepare the pattern for <n/m> and <xx>j
    repeatRE = re.compile(r'([0-9]+)/([0-9]+|[nN]) +([0-9]+)j')

    vdate = None
    vtype = vvisit.vtype
    vcomm = vvisit.comments
    vres = ""

    # auto-plan the next visit, if needed

    # these two types are mutually exclusive, we should probably check and report an error if
    # an visit is planned/executed for these two at the same time (same with 1, actually)
    if vetIsRappelAnn(vtype) or vetIsRappel1(vtype):
        # rappel annuel is always replanned for next year, 1er rappel replans a rappel annuel
        vdate = vvisit.vdate + timedelta(days=365)
        vtype = '--R-----'
        vcomm = ""

    elif vetIsPrimo(vtype):
        # primo vaccination always auto-plans 1er rappel 28 days later
        vdate = vvisit.vdate + timedelta(days=28)
        vtype = '-1------'
        vcomm = ""

    # if needed, auto-plan one of these
    if vdate:
       # generate the record and the event
        theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vvisit.vet_id, vtype=vtype,
            vdate=vdate, planned=True, comments=vcomm)
        db.session.add(theVisit)

        vres = vres + " +aP[{}]".format(vtype)

    # for the rest, only X and D should be replanned, and only if it's indicated in the comments
    vdate = None
    vtype = vvisit.vtype
    vcomm = vvisit.comments

    if vetIsSoins(vtype) or vetIsDepara(vtype):
        match = repeatRE.search(vcomm)
        if match:
            vnum = int(match.group(1))
            vmax = match.group(2)
            ddays = int(match.group(3))

            # determine if the replanning should take place
            if vmax == 'n' or vmax == 'N' or vnum < int(vmax):
                # define the new date and prepare the new comment
                vdate = vvisit.vdate + timedelta(days=ddays)
                vcomm = vcomm.replace("{}/{}".format(vnum, vmax), "{}/{}".format(vnum+1,vmax))
                # kill any non-X non-D
                vtype = '------' + vtype[-2:]

    # check if we have to add the planned visit
    if vdate:
       # generate the record and the event
        theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vvisit.vet_id, vtype=vtype,
            vdate=vdate, planned=True, comments=vcomm)
        db.session.add(theVisit)

        vres = vres + " +aP[{}]".format(vtype)

    return vres


def isValidCage(cageid):
    return cageid in [c[0] for c in TabCage]

def getViewUser():
    # check session variables to see if we are seeing our cats or someone else's
    FAid = current_user.id
    theFA = current_user

    if "otherFA" in session:
        FAid = session["otherFA"]
        theFA = User.query.filter_by(id=FAid).first()

        if theFA == None:
            return (None, None)

        # check access
        catMode, vetMode, searchMode = accessPrivileges(theFA)

        # if cat access is none, forget this
        if catMode == ACC_NONE:
            FAid = current_user.id
            theFA = current_user

    return (FAid, theFA)

def updatePrivilege(oldpriv, priv):
    return max(oldpriv, priv)

def accessPrivileges(fauser):
    # returns the access mode(s) for the current user vs cats owned by fauser (which can be == current user)
    # the parameters are:
    # catMode = ACC_NONE (no access)
    #         = ACC_RO (read-only access to the data)
    #         = ACC_MOD (access and modify cat data)
    #         = ACC_FULL (as above, but also add unreg cats)
    #         = ACC_TOTAL (all + move around + event history)
    # vetMode = ACC_NONE (no access)
    #         = ACC_RO (read-only access to the list)
    #         = ACC_MOD (can plan/delete)
    #         = ACC_FULL (can authorize bvet visits/print bonvet/....)
    #         = ACC_TOTAL (can generate unreg bonvets/unplanned bonvets)
    # searchMode = ACC_NONE (no searches)
    #         = ACC_RO (can view tables)
    #         = ACC_FULL (can search for information)
    #         = ACC_TOTAL (can search for select and do)

    if current_user.FAisADM:
        # total acces to anything, quick return
        return (ACC_TOTAL, ACC_TOTAL, ACC_TOTAL)

    catMode = ACC_NONE
    vetMode = ACC_NONE
    searchMode = ACC_NONE

    if current_user.FAisOV:
        # almost total access, except new reg and move around
        catMode = updatePrivilege(catMode, ACC_MOD)
        vetMode = updatePrivilege(vetMode, ACC_TOTAL)
        searchMode = updatePrivilege(searchMode, ACC_TOTAL)

    if current_user.FAisRF:
        # RF can access own and own FAs cats + auth  + access r/o AD/DCD/Refuge)
        if current_user.id == fauser.id or current_user.id == fauser.FAresp_id:
            catMode = updatePrivilege(catMode, ACC_MOD)
            vetMode = updatePrivilege(vetMode, ACC_FULL)

        elif isAdoptes(fauser.id) or isDecedes(fauser.id) or isRefuge(fauser.id) or isFATemp(fauser.id):
            catMode = updatePrivilege(catMode, ACC_RO)
            vetMode = updatePrivilege(vetMode, ACC_RO)

        searchMode = updatePrivilege(searchMode, ACC_RO)

    if current_user.FAisREF and current_user.id == fauser.id:
        # RF has full access of own cats
        catMode = updatePrivilege(catMode, ACC_FULL)
        vetMode = updatePrivilege(vetMode, ACC_FULL)
        searchMode = updatePrivilege(searchMode, ACC_RO)

    if current_user.FAisFA and current_user.id == fauser.id:
        # access to own cats
        catMode = updatePrivilege(catMode, ACC_MOD)
        vetMode = updatePrivilege(vetMode, ACC_MOD)

    if current_user.FAisVET:
        # vet cannot change cat data, but can mark visits as done (so it has planning ability)
        catMode = updatePrivilege(catMode, ACC_RO)
        vetMode = updatePrivilege(vetMode, ACC_MOD)
        # the code in veterinary.py will additionally verify that the visit is associated to the vet himself

    return (catMode, vetMode, searchMode)
