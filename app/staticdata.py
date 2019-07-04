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


# constants
ACC_NONE = 0   # no access to data
ACC_RO = 1     # read-only (view) access
ACC_FULL = 2   # full access and edit, but not transfer
ACC_TOTAL = 3  # full access and transfer

# IMPORTANT: the special FAs are stored statically here, so this must be set with the correct IDs
# special FA ids (static): AD DCD HIST REF TEMP
FAidSpecial = [2, 5, 10, 18, 90]
