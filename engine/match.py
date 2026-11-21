"""Hakku rules engine.

Plain, explainable matching: every scheme's rules live in data/schemes.json.
No AI here and no scheme rules in Python.

Result status per scheme:
  "likely"  -> every rule that applies passes          ("Likely eligible")
  "maybe"   -> nothing fails, but some detail unknown  ("Might be eligible – check one thing")
  "no"      -> at least one rule fails                 ("Not a match right now")
"""
from __future__ import annotations

import json
import os
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SCHEMES_PATH = os.path.join(DATA_DIR, "schemes.json")

STATUS_LABEL = {
    "likely": "Likely eligible",
    "maybe": "Might be eligible – check one thing",
    "no": "Not a match right now",
}

FIELD_LABEL = {
    "education_level": "your course / class",
    "year": "your year of study",
    "community": "your community",
    "annual_income": "your family income",
    "gender": "your gender",
    "area": "whether you live in a rural or urban area",
    "district": "your district",
    "disability": "whether you have a disability (40%+)",
    "marks_percent": "your last exam marks",
    "college_type": "whether your school/college is government or private",
}

LEVEL_LABEL = {
    "class_9": "Class 9", "class_10": "Class 10", "inter": "Inter (11–12)",
    "iti_polytechnic": "ITI / Polytechnic", "degree": "Degree",
    "professional": "Engineering / Medical / Professional", "pg": "PG",
}

VALUE_LABEL = {
    "gender": {"female": "Female", "male": "Male", "other": "Other"},
    "area": {"rural": "Rural", "urban": "Urban"},
    "college_type": {"government": "Government / Aided", "private": "Private"},
    "education_level": LEVEL_LABEL,
}


def load_schemes(path: str = SCHEMES_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["schemes"]


def format_inr(n) -> str:
    s = str(int(n))
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "₹" + ",".join(parts) + "," + tail


def format_value(field: str, value) -> str:
    if value is None:
        return "not told yet"
    if field == "annual_income":
        return format_inr(value)
    if field == "marks_percent":
        return f"{value:g}%"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return VALUE_LABEL.get(field, {}).get(value, str(value))


def _known(value) -> bool:
    return value is not None and value != ""


def check(op: str, actual, expected) -> bool:
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected
    if op == "lte":
        return actual <= expected
    if op == "gte":
        return actual >= expected
    if op == "lt":
        return actual < expected
    if op == "gt":
        return actual > expected
    raise ValueError(f"Unknown operator in schemes.json: {op!r}")


def evaluate_condition(cond: dict, profile: dict):
    """True / False, or None when the profile does not have the field."""
    actual = profile.get(cond["field"])
    if not _known(actual):
        return None
    return check(cond["op"], actual, cond["value"])


def evaluate_rule(rule: dict, profile: dict, lang: str = "en"):
    """Returns a reason dict, or None if the rule does not apply to this person."""
    # only_if: the rule applies only when all of these conditions hold.
    conditions = rule.get("only_if") or []
    cond_results = [evaluate_condition(c, profile) for c in conditions]
    if any(r is False for r in cond_results):
        return None
    missing = [c["field"] for c, r in zip(conditions, cond_results) if r is None]

    field = rule["field"]
    actual = profile.get(field)
    template = rule.get(f"text_{lang}") or rule["text_en"]
    text = template.replace("{user_value}", format_value(field, actual))

    if not _known(actual):
        missing.append(field)
    if missing:
        return {"status": "unknown", "field": field, "missing": missing, "text": text}

    passed = check(rule["op"], actual, rule["value"])
    return {"status": "pass" if passed else "fail", "field": field, "missing": [], "text": text}


def applies(cond: dict | None, profile: dict) -> bool:
    """For optional items like documents: include unless the condition is known to be false."""
    if not cond:
        return True
    return evaluate_condition(cond, profile) is not False


def match_scheme(scheme: dict, profile: dict, lang: str = "en", today: date | None = None) -> dict:
    reasons = [r for r in (evaluate_rule(rule, profile, lang) for rule in scheme["rules"]) if r]
    failed = [r for r in reasons if r["status"] == "fail"]
    unknown = [r for r in reasons if r["status"] == "unknown"]

    if failed:
        status = "no"
    elif unknown:
        status = "maybe"
    else:
        status = "likely"

    missing_fields = []
    for r in unknown:
        for f in r["missing"]:
            if f not in missing_fields:
                missing_fields.append(f)

    days_left = None
    if scheme.get("deadline"):
        today = today or date.today()
        days_left = (date.fromisoformat(scheme["deadline"]) - today).days

    return {
        "id": scheme["id"],
        "name": scheme.get(f"name_{lang}") or scheme["name_en"],
        "name_en": scheme["name_en"],
        "status": status,
        "status_label": STATUS_LABEL[status],
        "reasons": reasons,
        "passed_count": sum(1 for r in reasons if r["status"] == "pass"),
        "rule_count": len(reasons),
        "failed": failed,
        "missing_fields": missing_fields,
        "missing_labels": [FIELD_LABEL.get(f, f) for f in missing_fields],
        "documents": [d for d in scheme.get("documents", []) if applies(d.get("needed_if"), profile)],
        "benefit_text": scheme.get("benefit_text"),
        "benefit_max_inr": scheme.get("benefit_max_inr", 0),
        "category": scheme.get("category"),
        "deadline": scheme.get("deadline"),
        "deadline_note": scheme.get("deadline_note"),
        "days_left": days_left,
        "source_name": scheme.get("source_name"),
        "source_url": scheme.get("source_url"),
        "last_verified": scheme.get("last_verified"),
    }


def _sort_key(result: dict):
    days = result["days_left"] if result["days_left"] is not None else 10**6
    return (days, -(result["benefit_max_inr"] or 0))


def match_all(profile: dict, schemes: list[dict] | None = None, lang: str = "en", today: date | None = None) -> dict:
    """Match a profile against every scheme. Returns results grouped and sorted."""
    schemes = schemes if schemes is not None else load_schemes()
    results = [match_scheme(s, profile, lang, today) for s in schemes]
    groups = {k: sorted([r for r in results if r["status"] == k], key=_sort_key) for k in ("likely", "maybe", "no")}
    likely_value = sum(r["benefit_max_inr"] or 0 for r in groups["likely"] if r["category"] != "loan")
    return {
        "likely": groups["likely"],
        "maybe": groups["maybe"],
        "no": groups["no"],
        "summary": {
            "likely_count": len(groups["likely"]),
            "maybe_count": len(groups["maybe"]),
            "likely_value_inr": likely_value,
            "likely_value_text": format_inr(likely_value),
        },
    }


def fields_that_matter(profile: dict, schemes: list[dict] | None = None) -> list[str]:
    """Missing profile fields that would change at least one result (for the Quick questions screen)."""
    schemes = schemes if schemes is not None else load_schemes()
    needed = []
    for s in schemes:
        result = match_scheme(s, profile)
        if result["status"] == "maybe":
            for f in result["missing_fields"]:
                if f not in needed:
                    needed.append(f)
    return needed
