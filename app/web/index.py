from app import app, db, login_manager, devel_site
from app.staticdata import TabColor, TabSex, TabHair
from app.models import User, Cat
from flask import render_template, redirect, request, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from urllib.parse import urlparse


def safe_next_url(target):
    """Return target if it is safe to redirect to, None otherwise.
    Accepted: relative paths of this site, and URLs on association-era.org subdomains
    (e.g. back to the adoptions site after login)."""
    if not target or '\\' in target:
        return None
    url = urlparse(target)
    if not url.scheme and not url.netloc:
        return target if target.startswith('/') and not target.startswith('//') else None
    host = url.hostname or ''
    if url.scheme in ('http', 'https') and (host == 'association-era.org' or host.endswith('.association-era.org')):
        return target
    return None


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(username=user_id).first()


@app.route('/adoptions', methods=["GET", "POST"])
def index():
    cats = []

    # TODO split in pages of 10 or something....
    return render_template("adopt_page.html", tabcol=TabColor, tabsex=TabSex, tabhair=TabHair, catlist=cats, devsite=devel_site)


@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        # remember where to go after login (e.g. adoptions site), the form does not forward it
        next_url = safe_next_url(request.args.get("next"))
        if next_url:
            session["login_next"] = next_url
        else:
            session.pop("login_next", None)
        return render_template("login_page.html", devsite=devel_site, error=False)

    user = load_user(request.form["username"])
    if user is None:
        return render_template("login_page.html", devsite=devel_site, error=True)

    if not user.check_password(request.form["password"]):
        return render_template("login_page.html", devsite=devel_site, error=True)

    login_user(user)

    # store last access and fix number of cats (just in case...)
    ncats = Cat.query.filter_by(owner_id=current_user.id).count()
    if ncats != current_user.numcats:
        current_user.numcats = ncats

    current_user.FAlastop = datetime.now()
    db.session.commit()

    # reset the session data
    session.pop("otherFA", None)
    session.pop("otherMode", None)
    session.pop("searchFilter", None)
    session.pop("optCOMPTA", None)
    session.pop("optVETOHIST", None)
    return redirect(session.pop("login_next", None) or url_for('fapage'))

@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(safe_next_url(request.args.get("next")) or url_for('fapage'))
