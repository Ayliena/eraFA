# --------------- STATIC DATA

# this maps DB field number to the string
# NOTE they must match the ones used in cat_page.html
DBTabColor = ["INCONNU", "BEIGE", "BEIGE ET BLANC", "BLANC", "BLUE POINT", "CREME", "ECAILLE DE TORTUE", "GRIS", "GRIS CHARTREUX", "GRIS ET BLANC",
             "NOIR", "NOIR ET BLANC", "NOIR ET SMOKE", "NOIR PLASTRON BLANC", "ROUX", "ROUX ET BLANC", "SEAL POINT", "TABBY BLANC", "TABBY BRUN", "TABBY GRIS",
             "TIGRE", "TIGRE BEIGE", "TIGRE BRUN", "TIGRE CREME", "TIGRE GRIS", "TRICOLORE"]
DBTabSex = ["INCONNU", "FEMELLE", "MALE"]
DBTabHair = ["COURT", "MI-LONG", "LONG"]

# these are the readable (html page) versions
TabColor = ["??couleur??", "Beige", "Beige et blanc", "Blanc", "Blue point", "Crème", "Ecaille de tortue", "Gris", "Gris chartreux", "Gris et blanc",
             "Noir", "Noir et blanc", "Noir et smoke", "Noir plastron blanc", "Roux", "Roux et blanc", "Seal point", "Tabby blanc", "Tabby brun", "Tabby gris",
             "Tigré", "Tigré beige", "Tigré brun", "Tigré crème", "Tigré gris", "Tricolore"]
TabSex = ["??sexe??", "Femelle", "Mâle"]
TabHair = ["", ", poil mi-long", ", poil long"]
#TabHair = ["COURT", "MI-LONG", "LONG"]

# ids and names of the cages
TabCage = [
    ("AXX", "Cage non definie"),
    ("B01", "Maternité 1"),
    ("B02", "Maternité 2"),
    ("B03", "Maternité 3"),
    ("B04", "Maternité 4"),
    ("B05", "Maternité 5"),
    ("B06", "Maternité 6"),
    ("BtA", "Maternité A"),
    ("BtB", "Maternité B"),
    ("G07", "Grande Piece 7"),
    ("G08", "Grande Piece 8"),
    ("G09", "Grande Piece 9"),
    ("G10", "Grande Piece 10"),
    ("G11", "Grande Piece 11"),
    ("G12", "Grande Piece 12"),
    ("G13", "Grande Piece 13"),
    ("G14", "Grande Piece 14"),
    ("G15", "Grande Piece 15"),
    ("G16", "Grande Piece 16"),
    ("G17", "Grande Piece 17"),
    ("G18", "Grande Piece 18"),
    ("G19", "Grande Piece 19"),
    ("G20", "Grande Piece 20"),
    ("G21", "Grande Piece 21"),
    ("G22", "Grande Piece 22"),
    ("GtC", "Grande Piece C"),
    ("GtD", "Grande Piece D"),
    ("P23", "Petite Piece 23"),
    ("P24", "Petite Piece 24"),
    ("P25", "Petite Piece 25"),
    ("P26", "Petite Piece 26"),
    ("P27", "Petite Piece 27"),
    ("P28", "Petite Piece 28"),
    ("P29", "Petite Piece 29"),
    ("P30", "Petite Piece 30"),
    ("P31", "Petite Piece 31"),
    ("P32", "Petite Piece 32"),
    ("P33", "Petite Piece 33"),
    ("P34", "Petite Piece 34"),
    ("PtE", "Petite Piece E"),
    ("PtF", "Petite Piece F"),
]


# constants (see helpers.py accessPrivileges)
ACC_NONE = 0
ACC_RO = 1
ACC_MOD  = 2
ACC_FULL = 3
ACC_TOTAL = 4

# empty vet visit type
NO_VISIT = '--------'

# database ID of special 'Aucun' and 'Generic' vet
NO_VET = 115
GEN_VET = 8

# IMPORTANT: the special FAs are stored statically here, so this must be set with the correct database IDs
# special FA ids (static): AD DCD HIST REF TEMP
FAidSpecial = [2, 5, 10, 18, 90]
