from app import app, db
from app.models import GlobalData, User
from app.helpers import getSpecialUser
from app.permissions import UT_FA, UT_REFUGE, UT_AD, UT_DCD, UT_RS, UT_HIST, UT_FATEMP, UT_VETO
#from socket import gethostname
from werkzeug.security import generate_password_hash
import string
import secrets
from datetime import datetime

if __name__ == '__main__':
#    file = open("testfile.txt", "w")
#    file.write("Now is {}\n".format(datetime.now()))
#    file.close()

    print("--- command-line exec mode ---")
    print("Generating db....")
    db.create_all()

    print("Initializing GlobalData....");
    globaldata = GlobalData.query.filter_by(id=1).first()
    if not globaldata:
        globaldata = GlobalData(id=1, LastImportReg=200001, LastImportDate=datetime.now(), LastSyncDate=datetime())

    print("Populating with default users....");

    userAD = getSpecialUser('ad')
    if not userAD:
        userAD = User(username="--adopted--", usertype=UT_AD, password_hash="nologinAD", FAname="Chats adoptes", FAid="ADOPTIONS", FAemail="invalid@invalid")
        db.session.add(userAD)

    userDCD = getSpecialUser('dcd')
    if not userDCD:
        userDCD = User(username="--decedes--", usertype=UT_DCD, password_hash="nologinDCD", FAname="Chats decedes", FAid="DECEDES", FAemail="invalid@invalid")
        db.session.add(userDCD)

    userRS = getSpecialUser('rs')
    if not userRS:
        userRS = User(username="--relaches--", usertype=UT_RS, password_hash="nologinRS", FAname="Chats relaches", FAid="RELACHES", FAemail="invalid@invalid")
        db.session.add(userRS)

    userHIST = getSpecialUser('hist')
    if not userHIST:
        userHIST = User(username="--historique--", usertype=UT_HIST, password_hash="nologinHIST", FAname="Chats: historique", FAid="HISTORIQUE", FAemail="invalid@invalid")
        db.session.add(userHIST)

    userREF = getSpecialUser('ref')
    if not userREF:
        userREF = User(username="--refuge--", usertype=UT_REFUGE, password_hash="nologinREF", FAname="Refuge ERA", FAid="REFUGE", FAemail="invalid@invalid")
        db.session.add(userREF)

    userTEMP = getSpecialUser('fatemp')
    if not userTEMP:
        userTEMP = User(username="--fatemp--", usertype=UT_FATEMP, password_hash="nologinTEMP", FAname="FA temporaires", FAid="FA_TEMP", FAemail="invalid@invalid")
        db.session.add(userTEMP)
    db.session.commit()

    userVETG = User.query.filter_by(username="genvet").first()
    if not userVETG:
        newuserVETG = User(username="genvet", usertype=UT_VETO, password_hash="nologin-genvet", FAname="Autre (commentaires)", FAid="Veto", FAemail="invalid@invalid")
        db.session.add(newuserVETG)

    userNOVET = User.query.filter_by(username="novet").first()
    if not userNOVET:
        newuserNOVET = User(username="novet", usertype=UT_VETO, password_hash="nologin-genvet", FAname="Fait au refuge ou FA", FAid="REFUGE/FA", FAemail="invalid@invalid")
        db.session.add(newuserNOVET)

    # add myself as admin with a password
    userADM = User.query.filter_by(username="alberto").first()
    if not userADM:
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for i in range(8))

        print("--> admin is alberto/{}".format(password))
        newuser = User(username="alberto", usertype=UT_FA, PrivStr="1011111000111111111111110111111111", password_hash=generate_password_hash(password), FAname="Alberto BARSELLA", FAid="ALBERTO", FAemail="ishark@free.fr", FAisFA=True, FAisRF=True, FAisOV=True, FAisADM=True)
        db.session.add(newuser)

    db.session.commit()

#newuser = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=False)

#    if 'liveconsole' not in gethostname():
#        app.run()
