import json
import os
from datetime import date

from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)

from engine.extract import PROFILE_KEYS, extract
from engine.ics import build_ics
from engine.match import (FIELD_LABEL, LEVEL_LABEL, DATA_DIR, fields_that_matter,
                          format_value, load_schemes, match_all, match_scheme)

app = Flask(__name__)
# The session only holds the student's answers (never ID numbers) on their own device.
app.secret_key = os.environ.get("SECRET_KEY", "arhata-dev-only-change-me")

# Options for the "Edit my details" form (value, label).
FIELD_OPTIONS = {
    "education_level": list(LEVEL_LABEL.items()),
    "year": [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th+")],
    "community": [(c, c if c != "OC" else "OC / General") for c in ["SC", "ST", "BC", "EBC", "Minority", "OC"]],
    "annual_income": [(90000, "Under ₹1L"), (125000, "₹1–1.5L"), (175000, "₹1.5–2L"), (225000, "₹2–2.5L"),
                      (300000, "₹2.5–3.5L"), (500000, "₹3.5–8L"), (900000, "Above ₹8L")],
    "gender": [("female", "Female"), ("male", "Male"), ("other", "Other")],
    "area": [("rural", "Village (rural)"), ("urban", "Town or city (urban)")],
    "disability": [(True, "Yes, 40%+"), (False, "No")],
    "marks_percent": [(45, "Under 50%"), (52, "50–55%"), (68, "55–80%"), (88, "80% or more")],
    "college_type": [("government", "Government / Aided"), ("private", "Private")],
}
CHIP_FIELDS = ["education_level", "year", "community", "annual_income", "gender", "area",
               "disability", "marks_percent", "college_type"]

# The Quick questions screen: asked only when a detail is missing AND it changes a result.
QUESTIONS = {
    "education_level": ("What are you studying now?", "Each scholarship is for certain classes or courses."),
    "year": ("Which year of the course?", "Some schemes are only for the first or second year."),
    "community": ("Which community are you from?", "Many Telangana scholarships are set aside for SC, ST, BC, EBC or minority students."),
    "annual_income": ("Family income in a year?", "Almost every scholarship has an income limit. A rough idea is enough."),
    "gender": ("Are you a girl or a boy?", "Some schemes, like AICTE Pragati, are only for girls."),
    "area": ("Where do you live?", "The income limit for BC, EBC and minority students is different in rural and urban areas."),
    "disability": ("A disability of 40% or more?", "Some schemes are for students with a disability certificate."),
    "marks_percent": ("Marks in your last exam?", "A few scholarships ask for a minimum percentage."),
    "college_type": ("Government or private college?", "NMMS is only for students in government or aided schools."),
}


def load_samples():
    with open(os.path.join(DATA_DIR, "samples.json"), encoding="utf-8") as f:
        return json.load(f)["samples"]


def scheme_by_id(scheme_id):
    return next((s for s in load_schemes() if s["id"] == scheme_id), None)


def current_profile():
    return session.get("profile") or {}


def _coerce(field, raw):
    if raw in (None, "", "unknown"):
        return None
    if field in ("year", "annual_income"):
        return int(raw)
    if field == "marks_percent":
        return float(raw)
    if field == "disability":
        return raw in (True, "true", "True", "1", "yes")
    return raw


BAND_EDGES = {
    # option value -> upper edge of that band; a typed value is shown as the band it falls in
    "annual_income": [(90000, 100000), (125000, 150000), (175000, 200000), (225000, 250000),
                      (300000, 350000), (500000, 800000), (900000, float("inf"))],
    "marks_percent": [(45, 49.99), (52, 54.99), (68, 79.99), (88, float("inf"))],
}


def selected_options(profile):
    """Which option in the edit form should be pre-selected for each field."""
    out = {}
    for f in CHIP_FIELDS:
        v = profile.get(f)
        if v is None:
            out[f] = None
        elif f in BAND_EDGES:
            out[f] = next(opt for opt, edge in BAND_EDGES[f] if v <= edge)
        elif f == "year":
            out[f] = min(int(v), 4)
        else:
            out[f] = v
    return out


def understood_chips(profile):
    chips = []
    for f in CHIP_FIELDS:
        v = profile.get(f)
        if v is None:
            continue
        label = format_value(f, v)
        if f == "year":
            label = f"Year {v}"
        elif f == "annual_income":
            label = f"{label} a year"
        elif f == "disability":
            label = "Disability 40%+" if v else "No disability"
        elif f == "marks_percent":
            label = f"{label} marks"
        chips.append(label)
    if profile.get("district"):
        chips.append(profile["district"])
    return chips


@app.context_processor
def inject_helpers():
    def nice_date(iso):
        if not iso:
            return ""
        return date.fromisoformat(iso).strftime("%-d %b %Y")
    return {"nice_date": nice_date}


@app.route("/")
def index():
    return render_template("home.html", samples=load_samples(), schemes=load_schemes(), page="find",
                           text=session.get("text", ""))


@app.route("/find", methods=["POST"])
def find():
    sample_id = request.form.get("sample")
    if sample_id:
        sample = next((s for s in load_samples() if s["id"] == sample_id), None)
        if not sample:
            abort(404)
        session["profile"] = dict(sample["profile"])
        session["text"] = sample["text"]
        session["removed_id"] = False
        session["sample_name"] = sample["name"]
    else:
        text = (request.form.get("text") or "").strip()
        if not text:
            return redirect(url_for("index"))
        result = extract(text)
        session["profile"] = result["profile"]
        session["text"] = text if not result["removed_id"] else ""
        session["removed_id"] = result["removed_id"]
        session["read_by"] = result["source"]
        session.pop("sample_name", None)
        session["skipped"] = []
        session["asked"] = {}
        if pending_questions(result["profile"], []):
            return redirect(url_for("questions"))
    return redirect(url_for("results"))


def pending_questions(profile, skipped):
    """Missing details that would change at least one result, in a sensible order."""
    matter = set(fields_that_matter(profile))
    return [f for f in QUESTIONS if f in matter and f not in skipped and profile.get(f) is None]


@app.route("/questions", methods=["GET", "POST"])
def questions():
    if not session.get("profile"):
        return redirect(url_for("index"))
    profile = dict(current_profile())
    skipped = list(session.get("skipped", []))
    if request.method == "POST":
        field = request.form.get("field")
        if field in QUESTIONS:
            if request.form.get("skip"):
                skipped.append(field)
            else:
                profile[field] = _coerce(field, request.form.get("value"))
                if profile[field] is None:
                    skipped.append(field)
            session["profile"] = profile
            session["skipped"] = skipped
        return redirect(url_for("questions"))
    pending = pending_questions(profile, skipped)
    if not pending:
        return redirect(url_for("results"))
    field = pending[0]
    asked = dict(session.get("asked", {}))
    asked[field] = True
    session["asked"] = asked
    step = len(asked)
    total = step + len(pending) - 1
    q, why = QUESTIONS[field]
    return render_template("questions.html", page="find", field=field, question=q, why=why,
                           options=FIELD_OPTIONS[field], step=step, total=total,
                           chips=understood_chips(profile), removed_id=session.get("removed_id", False))


@app.route("/profile", methods=["POST"])
def update_profile():
    profile = dict(current_profile())
    shown = selected_options(profile)
    for f in CHIP_FIELDS:
        if f in request.form:
            new = _coerce(f, request.form.get(f))
            if new != shown[f]:  # only overwrite what the student actually changed
                profile[f] = new
    session["profile"] = profile
    return redirect(url_for("results"))


@app.route("/results")
def results():
    profile = current_profile()
    if not session.get("profile"):
        return redirect(url_for("index"))
    result = match_all(profile)
    missing = [f for f in CHIP_FIELDS if profile.get(f) is None]
    return render_template("results.html", page="find", r=result, profile=profile,
                           chips=understood_chips(profile), options=FIELD_OPTIONS,
                           field_label=FIELD_LABEL, chip_fields=CHIP_FIELDS, missing=missing,
                           selected=selected_options(profile),
                           removed_id=session.pop("removed_id", False),
                           sample_name=session.get("sample_name"))


@app.route("/scheme/<scheme_id>")
def scheme_detail(scheme_id):
    scheme = scheme_by_id(scheme_id)
    if not scheme:
        abort(404)
    profile = current_profile()
    result = match_scheme(scheme, profile)
    return render_template("scheme.html", page="find", s=scheme, m=result,
                           has_profile=bool(session.get("profile")))


@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(silent=True) or {}
    return jsonify(extract(data.get("text", "")))


@app.route("/api/match", methods=["POST"])
def api_match():
    data = request.get_json(silent=True) or {}
    profile = {k: data.get("profile", {}).get(k) for k in PROFILE_KEYS}
    return jsonify(match_all(profile, lang=data.get("lang", "en")))


@app.route("/api/scheme/<scheme_id>")
def api_scheme(scheme_id):
    scheme = scheme_by_id(scheme_id)
    if not scheme:
        abort(404)
    return jsonify(scheme)


@app.route("/api/ics/<scheme_id>")
def api_ics(scheme_id):
    scheme = scheme_by_id(scheme_id)
    if not scheme:
        abort(404)
    ics = build_ics(scheme)
    if not ics:
        abort(404)
    return Response(ics, mimetype="text/calendar",
                    headers={"Content-Disposition": f"attachment; filename=arhata-{scheme_id}.ics"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=True, port=port)
