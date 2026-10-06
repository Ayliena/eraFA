from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair
from app.models import Cat
from app.helpers import getViewUser
from app.adoption import AdoptionCat, ADOPT_STATUS_LABELS, adopt_csrf_token, adopt_csrf_valid, \
    save_adoption_photo, photo_filenames, PhotoError, readable_age
from app.vetvisits import vetIsTest
from flask import render_template, redirect, request, url_for, session, abort
from flask_login import login_required, current_user
from datetime import date
import os
import re
import uuid

# cat sex in eraFA (cats.sex) -> adoption_cats.sex
SEX_TO_ADOPT = {1: 'FEMALE', 2: 'MALE'}

# yes / no / unknown fields of the form: (name, label, [(form value, label), ...])
COMMON_FIELDS = [
    ('good_with_cats', "Entente avec les chats", [('1', "Sociable"), ('0', "Non souhaité"), ('', "Inconnu")]),
    ('good_with_children', "Entente avec les enfants", [('1', "Sociable"), ('0', "Non recommandé"), ('', "Inconnu")]),
    ('outdoor_access', "Accès extérieur", [('1', "Nécessaire"), ('0', "Vie en intérieur"), ('', "Inconnu")]),
]
# the test is always done before adoption: no "unknown" value
TEST_FIELDS = [
    ('fiv', "Test FIV", [('0', "Négatif"), ('1', "Positif")]),
    ('felv', "Test FeLV", [('0', "Négatif"), ('1', "Positif")]),
]
SEX_CHOICES = [('MALE', "Mâle"), ('FEMALE', "Femelle")]

# positive test results are written in the comments ("FIV+", "Positif LEUCOSE", see help_page.html),
# negative ones are not written at all
FIV_POSITIVE = re.compile(r"FIV\s?\+", re.IGNORECASE)
FELV_POSITIVE = re.compile(r"(LEUCOSE|FeLV\s?\+)", re.IGNORECASE)

# a listing for a cat younger than this is questionable (warning only)
YOUNG_AGE_DAYS = 90


def form_to_bool(raw):
    return {'1': True, '0': False}.get(raw)


def adoption_owner():
    """FA whose cats are listed (self, or the FA viewed by a referent / supervisor), or 403."""
    FAid, theFA = getViewUser()
    if not FAid or not theFA.menuFA() or theFA.typeRefuge():
        abort(403)
    return FAid, theFA


def is_regular(cat):
    """Unregistered ('N') and private ('P') cats cannot be proposed for adoption."""
    return not cat.isUnreg() and not cat.isPrivate()


def locked_fields(cat):
    """Fields known in eraFA, which are not editable in the form (they must already be right in Refugilys)."""
    return {
        "name": bool(cat.name),
        "sex": cat.sex in SEX_TO_ADOPT,
        "birthdate": cat.birthdate is not None,
    }


def cat_warnings(cat):
    """Warnings shown in red (the listing is still allowed)."""
    warnings = []
    if cat.birthdate and cat.ageDays() < YOUNG_AGE_DAYS:
        warnings.append("Moins de 3 mois : une annonce est discutable à cet âge.")
    if not cat.identif:
        warnings.append("Chat non identifié : une annonce pour un chat non identifié est déconseillée (presque illégale).")
    return warnings


def test_results(cat):
    """Prefilled FIV / FeLV results ('1' positive, '0' negative), from the cat and vet visit comments."""
    texts = [cat.comments or ""] + [v.comments or "" for v in cat.vetvisits]
    return {
        "fiv": '1' if any(FIV_POSITIVE.search(t) for t in texts) else '0',
        "felv": '1' if any(FELV_POSITIVE.search(t) for t in texts) else '0',
    }


def last_fiv_test(cat):
    """Last done FIV/FeLV test visit of a cat (the result is not stored, only its date and comments)."""
    tests = [v for v in cat.vetvisits if not v.planned and v.vtype and vetIsTest(v.vtype)]
    return tests[-1] if tests else None


def existing_listings(cat_ids):
    """{cats.id: status} of the cats which already have an adoption listing (single query)."""
    if not cat_ids:
        return {}
    rows = AdoptionCat.query.with_entities(AdoptionCat.cat_id, AdoptionCat.status).filter(AdoptionCat.cat_id.in_(cat_ids)).all()
    return {cat_id: status for cat_id, status in rows}


@app.route("/annonce", methods=["GET"])
@login_required
def adopt_select():
    """List of the FA cats, to select the one(s) of a new adoption listing."""
    FAid, theFA = adoption_owner()
    cats = [c for c in Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all() if is_regular(c)]
    listings = existing_listings([c.id for c in cats])

    return render_template("adopt_select_page.html", devsite=devel_site, user=current_user, viewuser=theFA,
                           tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, cats=cats, listings=listings,
                           young={c.id for c in cats if c.birthdate and c.ageDays() < YOUNG_AGE_DAYS},
                           readable_age=readable_age,
                           statuslabels=ADOPT_STATUS_LABELS, msg=session.pop("pendingmessage", []))


@app.route("/annonce/creer", methods=["POST"])
@login_required
def adopt_create():
    """Creation form of an adoption listing (step 'form'), then creation of the UNDER_REVIEW entries (step 'save')."""
    FAid, theFA = adoption_owner()

    # selected cats: must belong to the FA and have no adoption listing yet
    try:
        cat_ids = sorted({int(x) for x in request.form.getlist("cat_ids")})
    except ValueError:
        abort(400)
    if not cat_ids:
        session["pendingmessage"] = [[2, "Sélectionnez au moins un chat pour créer une annonce."]]
        return redirect(url_for('adopt_select'))

    cats = Cat.query.filter(Cat.id.in_(cat_ids), Cat.owner_id == FAid).order_by(Cat.regnum).all()
    if len(cats) != len(cat_ids) or not all(is_regular(c) for c in cats):
        abort(403)
    already = existing_listings(cat_ids)
    if already:
        names = ", ".join(c.name or c.regStr() for c in cats if c.id in already)
        session["pendingmessage"] = [[3, "Une annonce existe déjà pour : {}.".format(names)]]
        return redirect(url_for('adopt_select'))

    errors = {}
    if request.form.get("step") == "save":
        if not adopt_csrf_valid(request.form.get("csrf_token")):
            abort(400)

        values, errors = parse_create_form(request.form, cats)
        photos = [f for f in request.files.getlist("photos") if f and f.filename]
        max_photos = app.config.get("ADOPT_MAX_PHOTOS", 6)
        if not photos:
            errors["photos"] = "Ajoutez au moins une photo."
        elif len(photos) > max_photos:
            errors["photos"] = "{} photos maximum.".format(max_photos)

        if not errors:
            try:
                created = create_listing(cats, values, photos)
            except PhotoError as e:
                errors["photos"] = "Une photo n'a pas pu être traitée : {}.".format(e)
            else:
                names = ", ".join(c.name for c in created)
                session["pendingmessage"] = [[0, "Annonce créée pour {} : elle sera visible sur le site des adoptions "
                                                 "après validation par un administrateur.".format(names)]]
                return redirect(url_for('adopt_select'))
    else:
        values = initial_values(cats)

    return render_template("adopt_create_page.html", devsite=devel_site, user=current_user, viewuser=theFA,
                           tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, cats=cats, values=values, errors=errors,
                           tests={c.id: last_fiv_test(c) for c in cats}, common_fields=COMMON_FIELDS,
                           locked={c.id: locked_fields(c) for c in cats}, warnings={c.id: cat_warnings(c) for c in cats},
                           young={c.id for c in cats if c.birthdate and c.ageDays() < YOUNG_AGE_DAYS},
                           readable_age=readable_age, test_fields=TEST_FIELDS, sex_choices=SEX_CHOICES, csrf_token=adopt_csrf_token(),
                           max_photos=app.config.get("ADOPT_MAX_PHOTOS", 6), msg=[])


def initial_values(cats):
    """Form values guessed from eraFA (name, sex, birthdate, test results), the others are asked."""
    values = {f: None for f, _, _ in COMMON_FIELDS}
    values["description"] = ""
    for c in cats:
        values[c.id] = dict(eraFA_values(c), breed="Européen", **test_results(c))
    return values


def eraFA_values(cat):
    """Name, sex and birthdate of a cat as known in eraFA (empty if unknown)."""
    return {
        "name": cat.name or "",
        "sex": SEX_TO_ADOPT.get(cat.sex, ""),
        "birthdate": cat.birthdate.strftime("%Y-%m-%d") if cat.birthdate else "",
    }


def parse_create_form(form, cats):
    """Read and check the submitted form: returns (values, errors)."""
    errors = {}
    values = {}
    for field, _, choices in COMMON_FIELDS:
        values[field] = form.get(field)
        if values[field] not in [v for v, _ in choices]:
            errors[field] = "Choisissez une valeur."
    values["description"] = form.get("description", "").strip()
    if not values["description"]:
        errors["description"] = "La description est obligatoire."

    for c in cats:
        p = "c{}_".format(c.id)
        v = {k: form.get(p + k, "").strip() for k in ("name", "sex", "birthdate", "breed")}
        # fields known in eraFA are not editable: the eraFA values are used, whatever was submitted
        known = eraFA_values(c)
        for field, is_locked in locked_fields(c).items():
            if is_locked:
                v[field] = known[field]
        for field, _, _ in TEST_FIELDS:
            v[field] = form.get(p + field)
        values[c.id] = v

        if not v["name"]:
            errors[p + "name"] = "Le nom est obligatoire."
        elif len(v["name"]) > 100:
            errors[p + "name"] = "100 caractères maximum."
        if v["sex"] not in [s for s, _ in SEX_CHOICES]:
            errors[p + "sex"] = "Choisissez le sexe."
        if not v["birthdate"]:
            errors[p + "birthdate"] = "La date de naissance est obligatoire (estimée si inconnue)."
        else:
            try:
                if date.fromisoformat(v["birthdate"]) > date.today():
                    errors[p + "birthdate"] = "La date ne peut pas être dans le futur."
            except ValueError:
                errors[p + "birthdate"] = "Date invalide."
        if len(v["breed"]) > 100:
            errors[p + "breed"] = "100 caractères maximum."
        for field, _, choices in TEST_FIELDS:
            if v[field] not in [x for x, _ in choices]:
                errors[p + field] = "Choisissez une valeur."
    return values, errors


def create_listing(cats, values, photos):
    """
    Create one UNDER_REVIEW adoption_cats entry per cat, linked together, sharing the common fields and
    the photos. Photos are processed first; on any error, the written files are removed and nothing is saved.
    """
    folder = app.config["ADOPT_UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)

    entries = []
    for c in cats:
        v = values[c.id]
        entries.append(AdoptionCat(
            uuid=str(uuid.uuid4()),  # set now: needed for the photo names and the links between cats
            cat_id=c.id,
            status='UNDER_REVIEW',
            name=v["name"],
            sex=v["sex"],
            birthdate=date.fromisoformat(v["birthdate"]) if v["birthdate"] else None,
            breed=v["breed"] or None,
            good_with_cats=form_to_bool(values["good_with_cats"]),
            good_with_children=form_to_bool(values["good_with_children"]),
            outdoor_access=form_to_bool(values["outdoor_access"]),
            fiv=form_to_bool(v["fiv"]),
            felv=form_to_bool(v["felv"]),
            description=values["description"],
            created_by=current_user.id,
        ))

    # photos shared by the listing, named after its first cat: Name_uuidstart_N.jpg
    first = entries[0]
    filenames = photo_filenames(folder, first.name, first.uuid, len(photos))
    written = []
    try:
        for upload, filename in zip(photos, filenames):
            path = os.path.join(folder, filename)
            save_adoption_photo(upload, path)
            written.append(path)

        for e in entries:
            e.photos = list(filenames)
            e.linked_cats = [o.uuid for o in entries if o is not e] or None
            db.session.add(e)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in written:
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    return entries
