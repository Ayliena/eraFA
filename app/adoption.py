# --- ADOPTION LISTINGS (eraAdopt website)
# Creation of the adoption listings from eraFA: model of the shared adoption_cats table, photo processing
# and anti-CSRF token of the creation form (eraFA has no global CSRF protection).

import hmac
import os
import re
import secrets
import unicodedata
import uuid
import warnings
from datetime import datetime

from flask import session
from app import db


class AdoptionCat(db.Model):
    """Adoption listing of a cat (table managed by eraAdopt, shared with eraFA)."""

    __tablename__ = "adoption_cats"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    cat_id = db.Column(db.Integer, nullable=True, index=True)  # cats.id
    status = db.Column(db.Enum('UNDER_REVIEW', 'ACCEPTED', 'ARCHIVED'), default='UNDER_REVIEW', nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sex = db.Column(db.Enum('MALE', 'FEMALE'), nullable=False)
    birthdate = db.Column(db.Date, nullable=True)
    breed = db.Column(db.String(100), nullable=True)
    good_with_cats = db.Column(db.Boolean, nullable=True)
    good_with_children = db.Column(db.Boolean, nullable=True)
    outdoor_access = db.Column(db.Boolean, nullable=True)
    fiv = db.Column(db.Boolean, nullable=True)
    felv = db.Column(db.Boolean, nullable=True)
    description = db.Column(db.Text, nullable=True)
    photos = db.Column(db.JSON(none_as_null=True), nullable=True)
    linked_cats = db.Column(db.JSON(none_as_null=True), nullable=True)
    created_by = db.Column(db.Integer, nullable=True)  # users.id
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return "<AdoptionCat {} ({})>".format(self.name, self.uuid)


# status labels, for the list of cats
ADOPT_STATUS_LABELS = {
    'UNDER_REVIEW': "Annonce en attente de validation",
    'ACCEPTED': "Annonce publiée",
    'ARCHIVED': "Annonce archivée",
}


# --- anti-CSRF token of the creation form

def adopt_csrf_token():
    if "adopt_csrf" not in session:
        session["adopt_csrf"] = secrets.token_urlsafe(32)
    return session["adopt_csrf"]


def adopt_csrf_valid(token):
    expected = session.get("adopt_csrf")
    return bool(expected) and bool(token) and hmac.compare_digest(expected, token)


# --- photos

PHOTO_MAX_SIDE = 1600       # longest side after resizing (px)
PHOTO_JPEG_QUALITY = 82
PHOTO_MAX_PIXELS = 60_000_000   # larger images are refused (except JPEG, decoded directly at a reduced size)


class PhotoError(Exception):
    pass


def slugify_name(name):
    """'Félix' -> 'Felix', 'Chloé & Minou' -> 'Chloe_Minou' (file names without accents)."""
    if not name:
        return "chat"
    text = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'\s+', '_', text.strip())
    text = re.sub(r'[^a-zA-Z0-9_-]', '', text)
    return text or "chat"


def save_adoption_photo(file_storage, dest_path):
    """
    Save an uploaded photo as JPEG: rotated upright (EXIF orientation), resized to PHOTO_MAX_SIDE and
    WITHOUT any metadata (EXIF, including the GPS position). Raises PhotoError if the file is not an accepted image.
    """
    from PIL import Image, ImageOps

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            img = Image.open(file_storage.stream)
            fmt = img.format
            if fmt not in ("JPEG", "MPO", "PNG", "WEBP"):
                raise PhotoError("format non pris en charge ({}) : utilisez une photo JPEG, PNG ou WebP".format(fmt or "inconnu"))

            if fmt in ("JPEG", "MPO"):
                # decode directly at a reduced size: little memory even for a very large photo
                img.draft("RGB", (PHOTO_MAX_SIDE * 2, PHOTO_MAX_SIDE * 2))
            elif img.width * img.height > PHOTO_MAX_PIXELS:
                raise PhotoError("image trop grande ({}x{} px)".format(img.width, img.height))

            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")

            img.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE), Image.LANCZOS)
            # no exif parameter: no metadata is written (only the color profile is kept)
            img.save(dest_path, "JPEG", quality=PHOTO_JPEG_QUALITY, optimize=True, progressive=True,
                     icc_profile=img.info.get("icc_profile"))
    except PhotoError:
        raise
    except Exception as e:
        raise PhotoError("fichier illisible ou image trop grande") from e


def photo_filenames(folder, cat_name, cat_uuid, count):
    """Free file names 'Name_uuidstart_N.jpg' for count photos."""
    base = "{}_{}".format(slugify_name(cat_name), cat_uuid.split('-')[0])
    names, i = [], 1
    while len(names) < count:
        candidate = "{}_{}.jpg".format(base, i)
        if not os.path.exists(os.path.join(folder, candidate)):
            names.append(candidate)
        i += 1
    return names
