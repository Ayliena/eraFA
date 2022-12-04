from app import app, db
from app.models import Event, VetInfo
from app.staticdata import NO_VISIT
from datetime import datetime, timedelta
from flask_login import current_user
import re

# --------------- VET VISIT HELPER FUNCTIONS

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
    res = ""
    for i in range(0,8):
        if str[i] == '-':
            res = res + vetstr2[i]
        else:
            res = res + str[i]

    return res


def vetSubStrings(vetstr1, vetstr2):
    res = ""
    for i in range(0,8):
        if str[i] != "-" and vetstr2[i] != "-":
            res = res + "-"
        else:
            res = res + str[i]

    return res


def vetIncludes(vetstr1, vetstr2):
    # determine if vetstr1 includes all the visit types of vetstr2
    for i in range(0,8):
        if vetstr2[i] != '-' and vetstr1[i] == '-':
            return False

    return True


def vetGetUnique(vetstr):
    Uniques = "V1PTSR"
    str = list(vetstr)
    res = ""

    for i in range(0,8):
        if str[i] != '-' and Uniques.find(str[i]) > 0:
            res = res + str[i]
        else:
            res = res + "-"

    return res


def vetGetNonUnique(vetstr):
    Uniques = "XD"
    str = list(vetstr)
    res = ""

    for i in range(0,8):
        if str[i] != '-' and Uniques.find(str[i]) > 0:
            res = res + str[i]
        else:
            res = res + "-"

    return res


# Visit management functions
#
# Basic ideas: there are two classes of visits: unique and non-unique
# unique visits: V 1 P T S R
# non-unique visits: X D
# technically R is not unique, but it's meaningless to multi-plan them one year in advance
#
# the difference is that if a unique-class visit is added (as executed or planned), any other planned visit of the same type is de-planned
# this does not apply to non-unique-class visits, for which multiple planned vists can coexist
#
# the two main management functions are:
# - adding a vet visit
# - updating an existing visit (change of type/date/state P->E)
#
# Special syntax in comments:
# - if the text of an executed visit contains <x/y> <zz>j an identical visit is automatically replanned
#   in the case of non-unique-class visits
# - if the text of a planned visit contains <x/y> *<zz>j then a sequence of identical visits is automatically
#   replanned
# The replanned visits are <zz> days in the future as compared as the processed visit and the replanning occurs
# increasing <x> until it's equal to <y>
# The special syntax "<x>/n" means infinitely recurring visits (as it would be for rappel annuel), and is only
# recognized for the first case (executed visit)
#
# None of the two special codes applies to unique-class visits, because it would have no sense

def cat_deleteVisit(theCat, theVisit, automode):
    # note: theVisit is the database objet and not an id

    # paranoia check, do nothing if this doesn't match
    if theVisit.cat_id != theCat.id:
        return False

    theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} annullée{}".format(current_user.FAname, theVisit.vtype,
        (" (auto)" if automode else "")))
    db.session.add(theEvent)
    db.session.delete(theVisit)
    db.session.commit()
    return True


def cat_plannedCleanup(theCat, vtype):
    # remove any unique-class planned visits which exist for theCat

    # remove all the non-unique-class visits from the request
    unique_vtype = vetGetUnique(vtype)

    vres = ""

    # check if we have something to remove
    if unique_vtype == NO_VISIT:
        return vres

    # now iterate on all the cat's planned vetvisits and remove the corresponding type
    # if this results in an empty visit, delete it
    vetvisits = VetInfo.query.filter_by(cat_id=theCat.id)

    for vv in vetvisits:
        # remove any duplicate
        newvtype = vetSubString(vv.vtype, unique_vtype)

        if newvtype == NO_VISIT:
            # nothing left, we can remove this
            vres += " aD[{}]".format(vv.vtype)
            cat_deleteVisit(theCat, vv)
        else:
            # keep anything which is still applicable
            vv.vtype = newvtype

    return vres

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

    # generate the record
    theVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vet.id, vtype=vtype, vdate=vdate,
        planned=vplan, comments=vcomm)

    # assume no additional return results
    vres = ""

    # two completely different approaches for planned or executed
    if vplan:
        # start with a cleanup of any duplicate unique visit
        cat_plannedCleanup(theCat, vtype)

        et = "planifiée pour le"
        # default state = not authorized
        theVisit.requested = False
        theVisit.transferred = False
        theVisit.validby_id = None

        # deal with multi-planning here
        # multi-planning is only possible for X and D
        if vetIsSoins(vtype) or vetIsDepara(vtype):
            # pattern for the <n/m> *<xx>j syntax
            repeatREstar = re.compile(r'([0-9]+)/([0-9]+|[nN]) +\* *([0-9]+)j')

            match = repeatREstar.search(vcomm)
            if match:
                vnum = int(match.group(1))
                vmax = match.group(2)
                ddays = int(match.group(3))

                # in the planned visits, remove the anything after the *
                vcomm = vcomm[:vcomm.rindex("*")]

                # iterate and generate all the visits
                for vn in range(vnum,vmax+1):
                    # define the new date and prepare the new comment
                    vdate = vvisit.vdate + timedelta(days=ddays)
                    vcomm = vcomm.replace("{}/{}".format(vnum, vmax), "{}/{}".format(vnum+1,vmax))
                    # kill any non-X non-D
                    vtype = '------' + vtype[-2:]

                # generate the record (but no event?)
                apVisit = VetInfo(cat_id=theCat.id, doneby_id=theCat.owner_id, vet_id=vvisit.vet_id, vtype=vtype,
                    vdate=vdate, planned=True, requested=False, transferred=False, validby_id=None, comments=vcomm)
                db.session.add(apVisit)

                vres = vres + " +aP[{}]".format(vtype)

    else:
        # if executed, then cumulate with the global and auto-plan next visit if needed
        et = "effectuée le"
        theCat.vetshort = vetAddStrings(theCat.vetshort, vtype)

        # the rest is performed in a separate function, which is also called when converting P->E
        vres = cat_executedPostProcess(theCat, theVisit)

    db.session.add(theVisit)
    db.session.commit()  # needed for vet.FAname
    # add it as event (planned or not)
    theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, vtype, et, vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
    db.session.add(theEvent)
    db.session.commit()

    return " +{}[{}]".format('P' if vplan else 'E', vtype) + vres


def cat_updateVetVisit(vvid, VETlist, theCat, vstate, vtype, vvet, vdate, vcomm):
    # get the visit we're supposed to update
    theVisit = VetInfo.query.filter_by(id=vvid).first()
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
        res = " -{}[{}]".format('P' if theVisit.planned else 'E', theVisit.vtype)
        cat_deleteVisit(theCat, theVisit, False)
        return res

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
        vres = cat_executedPostProcess(theCat, theVisit)

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
    theVisit = VetInfo.query.filter_by(id=vvid).first()
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
    vres = cat_executedPostProcess(theCat, theVisit)

    # generate the event and return the information
    theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etext="{}: visite vétérinaire {} {} {} chez {}".format(current_user.FAname, theVisit.vtype, et, theVisit.vdate.strftime("%d/%m/%y"), theVisit.vet.FAname))
    db.session.add(theEvent)

    return " *E[{}]".format(theVisit.vtype) + vres


# after recording an executed visit, see if we should auto-plan the next
def cat_executedPostProcess(theCat, vvisit):
    vres = ""

    # this should never happen....
    if vvisit.planned:
        return vres

    # prepare the pattern for <n/m> and <xx>j
    repeatRE = re.compile(r'([0-9]+)/([0-9]+|[nN]) +([0-9]+)j')

    vdate = None
    vtype = vvisit.vtype
    vcomm = vvisit.comments

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
