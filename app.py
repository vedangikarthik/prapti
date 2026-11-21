import hmac
import json
import os
from datetime import date, datetime

from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)

from engine.extract import PROFILE_KEYS, extract
from engine.ics import build_ics
from engine.match import (FIELD_LABEL, LEVEL_LABEL, DATA_DIR, SCHEMES_PATH, fields_that_matter,
                          format_value, load_schemes, match_all, match_scheme)

app = Flask(__name__)
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 180  # remember language and answers for 6 months
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


LANGS = ("en", "te", "hi")
with open(os.path.join(DATA_DIR, "i18n.json"), encoding="utf-8") as _f:
    I18N = {k: v for k, v in json.load(_f).items() if not k.startswith("_")}


def get_lang():
    lang = session.get("lang")
    if lang in LANGS:
        return lang
    best = request.accept_languages.best_match(["en", "te", "hi"]) if request else None
    return best if best in LANGS else "en"


def tr(key, lang=None, **kw):
    lang = lang or get_lang()
    entry = I18N.get(key)
    if entry is None:
        text = key
    else:
        text = entry.get(lang) if entry.get(lang) is not None else entry.get("en", key)
    if "n" in kw and "{schemes}" in text:
        kw["schemes"] = "scheme" if kw["n"] == 1 else "schemes"
    for k, v in kw.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def opt(label, lang=None):
    """Translate an answer label (e.g. 'Female', 'Under ₹1L')."""
    entry = I18N.get("opt." + label)
    if not entry:
        return label
    return entry.get(lang or get_lang()) or label


def load_samples():
    with open(os.path.join(DATA_DIR, "samples.json"), encoding="utf-8") as f:
        return json.load(f)["samples"]


def sample_display_name(sample_id, lang):
    sample = next((x for x in load_samples() if x["id"] == sample_id), None)
    if not sample:
        return None
    return sample.get(f"name_{lang}") or sample["name"]


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


def understood_chips(profile, lang=None):
    chips = []
    for f in CHIP_FIELDS:
        v = profile.get(f)
        if v is None:
            continue
        if f == "year":
            label = tr("chip.year", lang, n=v)
        elif f == "annual_income":
            label = tr("chip.income", lang, v=format_value(f, v))
        elif f == "disability":
            label = tr("chip.disabled" if v else "chip.not_disabled", lang)
        elif f == "marks_percent":
            label = tr("chip.marks", lang, v=format_value(f, v))
        else:
            label = opt(format_value(f, v), lang)
        chips.append(label)
    if profile.get("district"):
        chips.append(profile["district"])
    return chips


@app.context_processor
def inject_helpers():
    lang = get_lang()

    def nice_date(iso):
        if not iso:
            return ""
        return date.fromisoformat(iso).strftime("%-d %b %Y")

    js_keys = {k: (v.get(lang) if v.get(lang) is not None else v.get("en")) for k, v in I18N.items()
               if k.split(".")[0] in ("home", "soon", "det", "tr", "st", "adv", "nx", "dl")}
    return {"nice_date": nice_date, "lang": lang, "t": lambda key, **kw: tr(key, lang, **kw),
            "opt": lambda label: opt(label, lang), "js_text": js_keys}


@app.route("/lang/<code>")
def set_lang(code):
    if code in LANGS:
        session["lang"] = code
        session.permanent = True
    back = request.referrer or url_for("index")
    return redirect(back if back.startswith(request.host_url) else url_for("index"))


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
        session["sample_name"] = sample["id"]
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
    q, why = tr("q." + field), tr("why." + field)
    return render_template("questions.html", page="find", field=field, question=q, why=why,
                           options=FIELD_OPTIONS[field], step=step, total=total,
                           chips=understood_chips(profile, get_lang()), removed_id=session.get("removed_id", False))


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
    lang = get_lang()
    result = match_all(profile, lang=lang)
    missing = [f for f in CHIP_FIELDS if profile.get(f) is None]
    return render_template("results.html", page="find", r=result, profile=profile,
                           chips=understood_chips(profile, lang), options=FIELD_OPTIONS,
                           field_label=FIELD_LABEL, chip_fields=CHIP_FIELDS, missing=missing,
                           selected=selected_options(profile),
                           removed_id=session.pop("removed_id", False),
                           sample_name=sample_display_name(session.get("sample_name"), lang))


@app.route("/scheme/<scheme_id>")
def scheme_detail(scheme_id):
    scheme = scheme_by_id(scheme_id)
    if not scheme:
        abort(404)
    profile = current_profile()
    result = match_scheme(scheme, profile, get_lang())
    return render_template("scheme.html", page="find", s=scheme, m=result,
                           has_profile=bool(session.get("profile")))


@app.route("/tracker")
def tracker():
    """The tracker lives on the student's own device (localStorage); the page only needs scheme facts."""
    meta = []
    today = date.today()
    lang = get_lang()
    for s in load_schemes():
        meta.append({
            "id": s["id"],
            "name": s.get(f"name_{lang}") or s["name_en"],
            "benefit": s.get("benefit_text"),
            "deadline": s.get("deadline"),
            "deadline_note": s.get("deadline_note"),
            "days_left": (date.fromisoformat(s["deadline"]) - today).days if s.get("deadline") else None,
            "documents": [{"name": d["name"], "hint": d.get("hint", "")} for d in s.get("documents", [])],
            "portal": next((st["link"] for st in s.get("steps", []) if st.get("link")), s.get("source_url")),
            "source_name": s.get("source_name"),
        })
    return render_template("tracker.html", page="tracker", schemes_meta=meta)


# ---------- About ----------
@app.route("/about")
def about():
    seen, sources = set(), []
    for sch in load_schemes():
        if sch["source_url"] not in seen:
            seen.add(sch["source_url"])
            sources.append((sch["source_name"], sch["source_url"]))
    return render_template("about.html", page="about", sources=sources)


# ---------- Helper mode (NGO / Mee Seva operators) ----------
@app.route("/helper")
def helper():
    return render_template("helper.html", page="helper")


@app.route("/api/helper-check", methods=["POST"])
def api_helper_check():
    data = request.get_json(silent=True) or {}
    extracted = extract(data.get("text", ""))
    result = match_all(extracted["profile"], lang="en")
    upcoming = sorted([m for m in result["likely"] if m["deadline"] and (m["days_left"] or 0) >= 0],
                      key=lambda m: m["days_left"])
    return jsonify({
        "chips": understood_chips(extracted["profile"], "en"),
        "likely": [{"id": m["id"], "name": m["name_en"]} for m in result["likely"]],
        "maybe": len(result["maybe"]),
        "value": result["summary"]["likely_value_inr"],
        "next_deadline": date.fromisoformat(upcoming[0]["deadline"]).strftime("%-d %b %Y") if upcoming else None,
        "removed_id": extracted["removed_id"],
    })


@app.route("/helper/print")
def helper_print():
    ids = [i for i in (request.args.get("ids") or "").split(",") if i]
    nick = (request.args.get("nick") or "Student")[:40]
    schemes = [sch for sch in load_schemes() if sch["id"] in ids]
    return render_template("print.html", nick=nick, schemes=schemes,
                           today=date.today().strftime("%-d %b %Y"))


# ---------- Scheme editor ----------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "arhata-demo")
CHANGELOG_PATH = os.path.join(DATA_DIR, "changelog.json")
OPS = ["eq", "in", "lte", "gte", "lt", "gt"]
RULE_FIELDS = ["education_level", "year", "community", "annual_income", "gender", "area",
               "disability", "marks_percent", "college_type"]


def _is_admin():
    return session.get("admin") is True


def _read_log():
    try:
        with open(CHANGELOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _parse_value(op, raw):
    raw = (raw or "").strip()
    def one(v):
        v = v.strip()
        if v.lower() in ("true", "false"):
            return v.lower() == "true"
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v
    if op == "in":
        return [one(v) for v in raw.split(",") if v.strip()]
    return one(raw)


@app.route("/admin/login", methods=["POST"])
def admin_login():
    if hmac.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
        session["admin"] = True
        return redirect(url_for("admin_schemes"))
    return render_template("admin_login.html", page="admin", error="That password is not right."), 401


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/admin/schemes")
def admin_schemes():
    if not _is_admin():
        return render_template("admin_login.html", page="admin")
    today = date.today()
    schemes = load_schemes()
    for sch in schemes:
        lv = sch.get("last_verified")
        sch["stale"] = (not lv) or (today - date.fromisoformat(lv)).days > 90
    return render_template("admin_list.html", page="admin", schemes=schemes, log=_read_log()[:12],
                           saved=request.args.get("saved"), default_password=ADMIN_PASSWORD == "arhata-demo")


@app.route("/admin/schemes/<scheme_id>", methods=["GET", "POST"])
def admin_edit(scheme_id):
    if not _is_admin():
        return render_template("admin_login.html", page="admin")
    with open(SCHEMES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    sch = next((x for x in data["schemes"] if x["id"] == scheme_id), None)
    if not sch:
        abort(404)
    if request.method == "GET":
        return render_template("admin_edit.html", page="admin", s=sch, fields=RULE_FIELDS, ops=OPS)

    form = request.form
    changes = []
    try:
        deadline = form.get("deadline", "").strip() or None
        if deadline:
            date.fromisoformat(deadline)
        updates = {
            "benefit_text": form.get("benefit_text", "").strip(),
            "benefit_max_inr": int(form.get("benefit_max_inr") or 0),
            "deadline": deadline,
            "deadline_note": form.get("deadline_note", "").strip(),
            "source_url": form.get("source_url", "").strip(),
        }
        if not updates["source_url"].startswith("https://"):
            raise ValueError("The official source must be an https:// link.")
        for k, v in updates.items():
            if sch.get(k) != v:
                changes.append(f"{k} {sch.get(k)!r} → {v!r}")
                sch[k] = v
        for i, rule in enumerate(sch["rules"]):
            op = form.get(f"op_{i}", rule["op"])
            field = form.get(f"field_{i}", rule["field"])
            if op not in OPS or field not in RULE_FIELDS:
                raise ValueError("Unknown field or check.")
            value = _parse_value(op, form.get(f"value_{i}"))
            text = form.get(f"text_{i}", rule["text_en"]).strip()
            if "{user_value}" not in text:
                raise ValueError(f"Rule {i + 1}: keep {{user_value}} in the sentence.")
            for k, v in (("field", field), ("op", op), ("value", value), ("text_en", text)):
                if rule.get(k) != v:
                    changes.append(f"rule {i + 1} {k} {rule.get(k)!r} → {v!r}")
                    rule[k] = v
    except ValueError as exc:
        return render_template("admin_edit.html", page="admin", s=sch, fields=RULE_FIELDS, ops=OPS,
                               error=str(exc) or "Please check the values."), 400

    sch["last_verified"] = date.today().isoformat()
    changes.append("marked verified")
    with open(SCHEMES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log = _read_log()
    log.insert(0, {"when": datetime.now().strftime("%Y-%m-%d %H:%M"), "scheme": sch["name_en"], "changes": changes})
    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log[:200], f, ensure_ascii=False, indent=2)
    return redirect(url_for("admin_schemes", saved=sch["name_en"]))


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
