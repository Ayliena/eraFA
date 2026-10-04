from app import app, db, devel_site
from app.staticdata import TabColor, TabSex, TabHair
from app.models import Cat
from app.helpers import getViewUser
from app.adoption import AdoptionCat, ADOPT_STATUS_LABELS, adopt_csrf_token, adopt_csrf_valid, \
    save_adoption_photo, photo_filenames, PhotoError
from app.vetvisits import vetIsTest
from flask import render_template, redirect, request, url_for, session, abort
from flask_login import login_required, current_user
from datetime import date
import os
import uuid

# cat sex in eraFA (cats.sex) -> adoption_cats.sex
SEX_TO_ADOPT = {1: 'FEMALE', 2: 'MALE'}

# yes / no / unknown fields of the form: (name, label, [(form value, label), ...])
COMMON_FIELDS = [
    ('good_with_cats', "Entente avec les chats", [('1', "Sociable"), ('0', "Non souhaité"), ('', "Inconnu")]),
    ('good_with_children', "Entente avec les enfants", [('1', "Sociable"), ('0', "Non recommandé"), ('', "Inconnu")]),
    ('outdoor_access', "Accès extérieur", [('1', "Nécessaire"), ('0', "Vie en intérieur"), ('', "Inconnu")]),
]
TEST_FIELDS = [
    ('fiv', "Test FIV", [('0', "Négatif"), ('1', "Positif"), ('', "Inconnu")]),
    ('felv', "Test FeLV", [('0', "Négatif"), ('1', "Positif"), ('', "Inconnu")]),
]
SEX_CHOICES = [('MALE', "Mâle"), ('FEMALE', "Femelle")]


def form_to_bool(raw):
    return {'1': True, '0': False}.get(raw)


def adoption_owner():
    """FA whose cats are listed (self, or the FA viewed by a referent / supervisor), or 403."""
    FAid, theFA = getViewUser()
    if not FAid or not theFA.menuFA() or theFA.typeRefuge():
        abort(403)
    return FAid, theFA


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
    cats = Cat.query.filter_by(owner_id=FAid).order_by(Cat.regnum).all()
    listings = existing_listings([c.id for c in cats])

    return render_template("adopt_select_page.html", devsite=devel_site, user=current_user, viewuser=theFA,
                           tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, cats=cats, listings=listings,
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
    if len(cats) != len(cat_ids):
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
                           test_fields=TEST_FIELDS, sex_choices=SEX_CHOICES, csrf_token=adopt_csrf_token(),
                           max_photos=app.config.get("ADOPT_MAX_PHOTOS", 6), msg=[])


def initial_values(cats):
    """Form values guessed from eraFA (name, sex, birthdate), the others are asked."""
    values = {f: None for f, _, _ in COMMON_FIELDS}
    values["description"] = ""
    for c in cats:
        values[c.id] = {
            "name": c.name or "",
            "sex": SEX_TO_ADOPT.get(c.sex, ""),
            "birthdate": c.birthdate.strftime("%Y-%m-%d") if c.birthdate else "",
            "breed": "Européen",
            "fiv": None,
            "felv": None,
        }
    return values


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

    # photos shared by the listing, named after its first cat: Nom_debutUUID_N.jpg
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
