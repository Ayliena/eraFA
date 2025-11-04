# user types (defines the type of main page)

UT_MANAGER = 0
UT_FA = 1
UT_REFUGE = 2
UT_ADOPTES = 3
UT_DECEDES = 4
UT_HIST = 5
UT_FATEMP = 6
UT_VETO = 7

# 1st column is actually useless as UT_xxx can be used as an index
TabUserTypes = [
    (UT_MANAGER, "Acces"),  # donne acces au permissions, mais sans role specifique
    (UT_FA, "Famille d'Accueil"),
    (UT_REFUGE, "Refuge"),
    (UT_ADOPTES, "Adoptes"),
    (UT_DECEDES, "Decedes"),
    (UT_HIST, "Historique"),
    (UT_FATEMP, "FA Temporaires"),
    (UT_VETO, "Veterinaire")
]

# Provileges are stored in a string using '0' and '1', the initial NUM_MENUS character refer to accessible menus in the
# interface, while the subsequent characters are the privileges themselves
NUM_MENUS = 10
MENU_FA = 0       # liste chats + visites veto + registre des soins
MENU_RFA = 1      # FA suivies + adoptes + decedes + historique + arrivee chat (FA suivies) + search
MENU_REF = 2      # arrivee chat (refuge) + situation veto + planning veto + Bon S/C
MENU_COMPTA = 3   # factures
MENU_ADMIN = 4    # set regnum + arrivee chat (w/regnum) + users + admin functions + info on API access

PRIV_ADMIN = 11   # admin acces -> can do anything
PRIV_RFA = 12     # referent FA -> can manage FAs
PRIV_REF = 13     # refuge -> acces to refuge pages
PRIV_ADDCD = 14   # access to the specific AD / DCD special FAs
PRIV_HIST = 15    # access to the HIST special FA
PRIV_SEARCH = 16  # can search for information on all cats
PRIV_BSC = 17     # operations refuge -> bon sterilisation/castration
PRIV_RVETO = 18   # access to refuge/visites veto
PRIV_RPLAN = 19   # can plan visits for refuge
PRIV_REGNUM = 20  # can give a regnum to an unregistered cat
PRIV_APIR = 21    # api read access
PRIV_APIW = 22    # api write access
PRIV_ADDUNR= 23   # can add a new (unregistered) cat

PRIV_NUMBER = 24


# check that the privilieges definition for this user is correct
def checkPrivileges(user):
    # if length of string is less than PRIV_NUMBER, expend and pad with zeroes
    if len(user.PrivStr) < PRIV_NUMBER:
        user.PrivStr = user.PrivStr.rjust(PRIV_NUMBER, '0')
    return True

def setPrivilege(user, pn, val):
    checkPrivileges(user)
    # validate
    if pn >= len(user.PrivStr):
        return False

    # note: we don't check if it was already set/unset
    nps = user.PrivStr[:pn] + ("1" if val else "0") + user.PrivStr[pn+1:]
    user.PrivStr = nps
    return True

def hasPrivilege(user, pn):
    if pn >= len(user.PrivStr):
        return False

    if user.PrivStr[pn] == '1':
        return True

    return False

def hasMenu(user, mn):
    if mn > NUM_MENUS:
        return False

    if user.PrivStr[mn] == '1':
        return True

    return False
