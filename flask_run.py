from app import app, db
from app.models import User
#from socket import gethostname
from werkzeug.security import generate_password_hash
import string
import secrets
#from datetime import datetime

if __name__ == '__main__':
#    file = open("testfile.txt", "w")
#    file.write("Now is {}\n".format(datetime.now()))
#    file.close()

    print("--- command-line exec mode ---")
    print("Generating db....")
    db.create_all()
    print("Populating with default users....");

    userAD = User.query.filter_by(FAisAD=True).first()
    if not userAD:
        userAD = User(username="--adopted--", password_hash="nologinAD", FAname="Chats adoptes", FAid="ADOPTIONS", FAemail="invalid@invalid", FAisAD=True)
        db.session.add(userAD)

    userDCD = User.query.filter_by(FAisDCD=True).first()
    if not userDCD:
        userDCD = User(username="--decedes--", password_hash="nologinDCD", FAname="Chats decedes", FAid="DECES", FAemail="invalid@invalid", FAisDCD=True)
        db.session.add(userDCD)

    userHIST = User.query.filter_by(FAisHIST=True).first()
    if not userHIST:
        userHIST = User(username="--historique--", password_hash="nologinHIST", FAname="Chats: historique", FAid="HISTORIQUE", FAemail="invalid@invalid", FAisHIST=True)
        db.session.add(userHIST)

    userREF = User.query.filter_by(FAisREF=True).first()
    if not userREF:
        userREF = User(username="--refuge--", password_hash="nologinREF", FAname="Refuge ERA", FAid="REFUGE", FAemail="invalid@invalid", FAisREF=True)
        db.session.add(userREF)

    userTEMP = User.query.filter_by(FAisTEMP=True).first()
    if not userTEMP:
        userTEMP = User(username="--fatemp--", password_hash="nologinTEMP", FAname="FA temporaires", FAid="FA_TEMP", FAemail="invalid@invalid", FAisTEMP=True)
        db.session.add(userTEMP)
    db.session.commit()

    print("--> make sure that staticdata.py contains: FAidSpecial = [{}, {}, {}, {}, {}]".format(userAD.id, userDCD.id, userHIST.id, userREF.id, userTEMP.id))

    userVETG = User.query.filter_by(username="genvet").first()
    if not userVETG:
        newuserVETG = User(username="genvet", password_hash="nologin-genvet", FAname="Autre (commentaires)", FAid="Veto", FAemail="invalid@invalid", FAisVET=True)
        db.session.add(newuserVETG)

    userNOVET = User.query.filter_by(username="novet").first()
    if not userNOVET:
        newuserNOVET = User(username="novet", password_hash="nologin-genvet", FAname="Fait au refuge ou FA", FAid="REFUGE/FA", FAemail="invalid@invalid", FAisVET=True)
        db.session.add(newuserNOVET)

    # add myself as admin with a password
    userADM = User.query.filter_by(username="alberto").first()
    if not userADM:
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for i in range(8))

        print("--> admin is alberto/{}".format(password))
        newuser = User(username="alberto", password_hash=generate_password_hash(password), FAname="Alberto BARSELLA", FAid="ALBERTO", FAemail="ishark@free.fr", FAisFA=True, FAisRF=True, FAisOV=True, FAisADM=True)
        db.session.add(newuser)

    db.session.commit()

#newuser = User(username="login", password_hash=generate_password_hash("password"), FAname="FA name - ERA", FAid="FA name - public", FAemail="FA email addr", FAisFA=True, FAisRF=False, FAisOV=False, FAisADM=False, FAisAD=False, FAisDCD=False, FAisVET=False, FAisHIST=False)

#    if 'liveconsole' not in gethostname():
#        app.run()
