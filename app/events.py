from app import app, db
from app.models import Cat, Event
from enum import IntEnum
from datetime import datetime

class ET(IntEnum):
    UNDEF       = 0
    ADD         = 1
    ADOPTE      = 2
    RELACHE     = 3
    DECEDE      = 4
    HISTORIQUE  = 5
    VET_PLAN    = 6
    VET_EXEC    = 7
    VET_DEL     = 8
    VET_BON     = 9
    TRANSFER    = 10
    UPDATE      = 11
    REGNUM      = 12
    CAGE        = 13

#
# date/time for the event being added is always "now"
#
def addEvent(theCat, ev_type, ev_text):
    theEvent = Event(cat_id=theCat.id, edate=datetime.now(), etype=ev_type, etext=ev_text)
    db.session.add(theEvent)
