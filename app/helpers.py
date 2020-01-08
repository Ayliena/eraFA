from app import app, db
from app.models import Event, VetInfo
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


def vetMapToString(vetmap, prefix):
    str =["-", "-", "-", "-", "-", "-", "-", "-"]
    if prefix+"_pv" in vetmap:
        str[0] = 'V'
    if prefix+"_r1" in vetmap:
        str[1] = '1'
    if prefix+"_r2" in vetmap:
        str[2] = '2'
    if prefix+"_sc" in vetmap:
        str[3] = 'S'
    if prefix+"_id" in vetmap:
        str[4] = 'P'
    if prefix+"_tf" in vetmap:
        str[5] = 'T'
    if prefix+"_gen" in vetmap:
        str[6] = 'X'
    if prefix+"_rr" in vetmap:
        str[7] = 'R'
    return "".join(str)

def vetStringToMap(vetstr, prefix):
    vmap = {}
    vmap[prefix+"_pv"] = (str[0] == 'V')
    vmap[prefix+"_r1"] = (str[1] == '1')
    vmap[prefix+"_r2"] = (str[2] == '2')
    vmap[prefix+"_sc"] = (str[3] == 'S')
    vmap[prefix+"_id"] = (str[4] == 'P')
    vmap[prefix+"_tf"] = (str[5] == 'T')
    vmap[prefix+"_gen"] = (str[6] == 'X')
    vmap[prefix+"_rr"] = (str[7] == 'R')
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

def cat_delete(theCat):
    # start by erasing the image (if any)
    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum))):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], "{}.jpg".format(theCat.regnum)))

    theCat.owner.numcats -= 1
    Event.query.filter_by(cat_id=theCat.id).delete()
    VetInfo.query.filter_by(cat_id=theCat.id).delete()
    db.session.delete(theCat)
    # note that WE DO NOT COMMIT
