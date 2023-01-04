from app import app, db
from app.models import User, Event, VetInfo
from app.staticdata import FAidSpecial, TabCage, ACC_NONE, ACC_RO, ACC_MOD, ACC_FULL, ACC_TOTAL
from sqlalchemy import and_, or_
from flask import session
from flask_login import current_user
from datetime import datetime
import hashlib
import base64
import os

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
