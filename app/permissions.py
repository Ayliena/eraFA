# user types (defines the type of main page)

UT_FA     = 0
UT_MANAGER= 1
UT_REFUGE = 2
UT_AD     = 3
UT_DCD    = 4
UT_RS     = 5
UT_HIST   = 6
UT_FATEMP = 7
UT_VETO   = 8

# the index must match the values above!
TabUserTypes = [
    "Famille d'Accueil",
    "Manager",
    "Refuge",
    "Adoptes",
    "Decedes",
    "Relaches",
    "Historique",
    "FA Temporaires",
    "Veterinaire"
]

# Provileges are stored in a string using '0' and '1', the initial NUM_MENUS character refer to accessible menus in the
# interface, while the subsequent characters are the privileges themselves
NUM_MENUS = 10
MENU_FA = 0       # liste chats + visites veto + registre des soins
MENU_VET = 1      # visites planifiees / historique
MENU_RFA = 2      # FA suivies + adoptes + decedes + historique + arrivee chat (FA suivies) + search
MENU_PROC = 3     # procedures: arrivee chat (refuge) + situation veto + planning veto + Bon S/C
MENU_COMPTA = 4   # factures
MENU_ADMIN = 5    # admin functions

PRIV_RFA     = 10   # referent FA -> can manage FAs
PRIV_RFATEMP = 11   # access to FAtemp
PRIV_SUPER   = 12   # superviseur -> r/w access to all FA and cats
PRIV_REF     = 13   # refuge -> acces to refuge page
PRIV_ADR     = 14   # access to the specific AD / DCD . RS special FAs
PRIV_HIST    = 15   # access to the HIST special FA
PRIV_SEARCH  = 16   # can search for information on all cats
PRIV_PEC     = 17   # procedure: PeC
PRIV_BSC     = 18   # procedure: bon post-ad
PRIV_CFA     = 19   # procedure: contrat FA
PRIV_CAD     = 20   # procedure: contrat adoption
PRIV_ADDCAT  = 21   # add an unregistered cat
PRIV_COMPTA  = 22   # access to the factures
PRIV_CMMOD   = 23   # can modify factures
PRIV_CMSELF  = 24   # can only see owned factures
PRIV_USERS   = 25   # can add/edit users
PRIV_ADMIN   = 26   # admin operations
PRIV_REGNUM  = 27   # can set regnum for a cat
PRIV_MOVE    = 28   # can transfer cats
PRIV_BVETO   = 29   # can generate bon veto/validate visit
PRIV_RVETO   = 30   # can plan visits for refuge
PRIV_APIR    = 31   # api read access
PRIV_APIW    = 32   # api write access

FIRST_PRIV = 10
NUM_PRIVS = 33

TabPrivs = [
    "MENU_FA",
    "MENU_VET",
    "MENU_RFA",
    "MENU_PROC",
    "MENU_COMPTA",
    "MENU_ADMIN",
    "",
    "",
    "",
    "",
    "RFA",
    "RFATEMP",
    "SUPER",
    "REF",
    "ADR",
    "HIST",
    "SEARCH",
    "PEC",
    "BSC",
    "CFA",
    "CAD",
    "ADDCAT",
    "COMPTA",
    "CMMOD",
    "CMSELF",
    "USERS",
    "ADMIN",
    "REGNUM",
    "MOVE",
    "BVETO",
    "RVETO",
    "APIR",
    "APIW"
]
