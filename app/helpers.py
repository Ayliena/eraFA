from app import app, db
from app.models import User, Event, VetInfo
from app.permissions import UT_REFUGE, UT_AD, UT_DCD, UT_RS, UT_HIST, UT_FATEMP, UT_VETO
from app.staticdata import TabCage
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
    if newFA.typeRefuge():
        theCat.temp_owner = TabCage[0][0]
    elif newFA.typeFAtemp():
        theCat.temp_owner = "FA INCONNUE"
    else:
        theCat.temp_owner = newFA.FAname

    if newFA.typeAdoptes() or newFA.typeDecedes() or newFA.typeRelaches() or newFA.typeHistorique():
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


def getSpecialUser(FAspec):
    theFA = None

    # generate the FAid
    if FAspec == 'ad':
        theFA = User.query.filter_by(usertype=UT_AD).first()
    elif FAspec == 'dcd':
        theFA = User.query.filter_by(usertype=UT_DCD).first()
    elif FAspec == 'rs':
        theFA = User.query.filter_by(usertype=UT_RS).first()
    elif FAspec == 'ref':
        theFA = User.query.filter_by(usertype=UT_REFUGE).first()
    elif FAspec == 'hist':
        theFA = User.query.filter_by(usertype=UT_HIST).first()
    elif FAspec == 'fatemp':
        theFA = User.query.filter_by(usertype=UT_FATEMP).first()

    return theFA


def getVeterinaireUsers():
    return User.query.filter_by(usertype=UT_VETO).order_by(User.FAname).all()


def getReferentUsers():
    # there's no easy way to filter this
    users = User.query.all()
    refusers = []

    for u in users:
        if u.hasReferent():
            refusers.append(u)

    return refusers


def getViewUser():
    # check session variables to see if we are seeing our cats or someone else's
    FAid = current_user.id
    theFA = current_user

    if "otherFA" in session:
        FAid = session["otherFA"]
        theFA = User.query.filter_by(id=FAid).first()

        if theFA == None:
            FAid = current_user.id
            theFA = current_user

        else:
            # make sure that you can access this FA
            if current_user.hasSuperviseur():
                pass

            elif theFA.typeRefuge() and current_user.hasRefuge():
                pass

            elif theFA.typeFAtemp() and current_user.hasReferentFAtemp():
                pass

            elif (theFA.typeAdoptes() or theFA.typeDecedes() or theFA.typeRelaches()) and current_user.hasAdDcdRs():
                pass

            elif theFA.typeHistorique() and current_user.hasHist():
                pass

            elif current_user.hasReferent() and theFA.resp_id == current_user.id:
                pass

            else:
                FAid = current_user.id
                theFA = current_user

    return (FAid, theFA)


# cat access modes (none, read-only, modify)
ACC_NONE = 0
ACC_RO = 1
ACC_MOD  = 2

# single cat version: determine if the user has acces to the specific cat

def canAccessCat(cat, user):
    # access always goes through who owns the cat
    return canAccessCats(cat.owner, user)


# multiple cat version: determine if the user has access to the cats of 'owner'
def canAccessCats(owner, user):
    # you can always access your own cats
    if user.id == owner.id:
        return ACC_MOD

    if user.hasReferent() and owner.FAresp_id == user.id:
        return ACC_MOD

    # refuge access
    if user.hasRefuge() and owner.typeRefuge():
        return ACC_MOD

    if user.hasReferentFAtemp() and owner.typeFAtemp():
        return ACC_MOD

    if user.hasSuperviseur():
        return ACC_MOD

    # referents have RO access to anything
    if user.hasReferent():
        return ACC_RO

    return ACC_NONE


# def updatePrivilege(oldpriv, priv):
#     return max(oldpriv, priv)


# def accessPrivileges(fauser):
#     # returns the access mode(s) for the current user vs cats owned by fauser (which can be == current user)
#     # the parameters are:
#     # catMode = ACC_NONE (no access)
#     #         = ACC_RO (read-only access to the data)
#     #         = ACC_MOD (access and modify cat data)
#     #         = ACC_FULL (as above, but also add unreg cats)
#     #         = ACC_TOTAL (all + move around + event history)
#     # vetMode = ACC_NONE (no access)
#     #         = ACC_RO (read-only access to the list)
#     #         = ACC_MOD (can plan/delete)
#     #         = ACC_FULL (can authorize bvet visits/print bonvet/....)
#     #         = ACC_TOTAL (can generate unreg bonvets/unplanned bonvets)
#     # searchMode = ACC_NONE (no searches)
#     #         = ACC_RO (can view tables)
#     #         = ACC_FULL (can search for information)
#     #         = ACC_TOTAL (can search for select and do)

#     if current_user.FAisADM:
#         # total acces to anything, quick return
#         return (ACC_TOTAL, ACC_TOTAL, ACC_TOTAL)

#     catMode = ACC_NONE
#     vetMode = ACC_NONE
#     searchMode = ACC_NONE

#     if current_user.FAisOV:
#         # almost total access, except new reg and move around
#         catMode = updatePrivilege(catMode, ACC_FULL)
#         vetMode = updatePrivilege(vetMode, ACC_TOTAL)
#         searchMode = updatePrivilege(searchMode, ACC_TOTAL)

#     if current_user.FAisRF:
#         # RF can access own and own FAs cats + auth + access r/o AD/DCD)
#         if current_user.id == fauser.id or current_user.id == fauser.FAresp_id or isRefuge(fauser.id):
#             catMode = updatePrivilege(catMode, ACC_MOD)
#             vetMode = updatePrivilege(vetMode, ACC_FULL)

#         elif isAdoptes(fauser.id) or isDecedes(fauser.id) or isFATemp(fauser.id):
#             catMode = updatePrivilege(catMode, ACC_RO)
#             vetMode = updatePrivilege(vetMode, ACC_RO)

#         searchMode = updatePrivilege(searchMode, ACC_RO)

#     if current_user.FAisREF and current_user.id == fauser.id:
#         # RF has full access of own cats
#         catMode = updatePrivilege(catMode, ACC_FULL)
#         vetMode = updatePrivilege(vetMode, ACC_FULL)
#         searchMode = updatePrivilege(searchMode, ACC_RO)

#     if current_user.FAisFA and current_user.id == fauser.id:
#         # access to own cats
#         catMode = updatePrivilege(catMode, ACC_MOD)
#         vetMode = updatePrivilege(vetMode, ACC_MOD)

#     if current_user.FAisVET:
#         # vet cannot change cat data, but can mark visits as done (so it has planning ability)
#         catMode = updatePrivilege(catMode, ACC_RO)
#         vetMode = updatePrivilege(vetMode, ACC_MOD)
#         # the code in veterinary.py will additionally verify that the visit is associated to the vet himself

#     return (catMode, vetMode, searchMode)
