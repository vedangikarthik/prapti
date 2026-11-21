"""Optional AI pass: read a student's plain-language message into the profile fields.

The AI only *reads* the message. It never decides eligibility: that stays in
engine/match.py, driven by data/schemes.json.

Runs only when Anthropic credentials are configured (ANTHROPIC_API_KEY or
ANTHROPIC_AUTH_TOKEN, or ARHATA_AI=on for an `ant auth login` profile).
Any problem (no SDK, no credentials, timeout, refusal) returns None and the
offline parser in engine/extract.py is used instead.
"""
from __future__ import annotations

import json
import os

MODEL = os.environ.get("ARHATA_MODEL", "claude-opus-5-5")

LEVELS = ["class_9", "class_10", "inter", "iti_polytechnic", "degree", "professional", "pg"]
COMMUNITIES = ["SC", "ST", "BC", "EBC", "Minority", "OC"]


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


SCHEMA = {
    "type": "object",
    "properties": {
        "education_level": _nullable({"type": "string", "enum": LEVELS}),
        "year": _nullable({"type": "integer"}),
        "community": _nullable({"type": "string", "enum": COMMUNITIES}),
        "annual_income": _nullable({"type": "integer"}),
        "gender": _nullable({"type": "string", "enum": ["female", "male", "other"]}),
        "area": _nullable({"type": "string", "enum": ["rural", "urban"]}),
        "district": _nullable({"type": "string"}),
        "disability": _nullable({"type": "boolean"}),
        "marks_percent": _nullable({"type": "number"}),
        "college_type": _nullable({"type": "string", "enum": ["government", "private"]}),
    },
    "required": ["education_level", "year", "community", "annual_income", "gender", "area",
                 "district", "disability", "marks_percent", "college_type"],
    "additionalProperties": False,
}

SYSTEM = """You read short messages from students in Telangana, India, written in English, Telugu, Hindi or a mix, and fill in a profile used to check government scholarship eligibility.

Fill a field only when the message states it or makes it unmistakable; otherwise use null. Never guess.
- education_level: class_9, class_10, inter (Intermediate / Class 11-12 / junior college), iti_polytechnic (ITI, polytechnic, diploma), degree (BA, BCom, BSc and similar), professional (engineering, B.Tech, medicine, pharmacy, nursing and similar), pg (any master's).
- year: year of the current course as a number.
- community: SC, ST, BC (any BC-A to BC-E, OBC), EBC, Minority (Muslim, Christian, Sikh and other minorities), OC (general / forward caste).
- annual_income: yearly family income in rupees as a whole number. 1 lakh = 100000; "80 వేలు" or "80 हज़ार" = 80000. If a monthly figure is given, multiply by 12.
- gender: from words like girl/boy, or Hindi verb forms such as "कर रही हूँ" (female) and "कर रहा हूँ" (male).
- area: rural for a village; urban for a city or town. Hyderabad is urban.
- district: the Telangana district name in English, if mentioned.
- disability: true only if a disability is mentioned; false only if the student says they have none.
- marks_percent: the most recent exam percentage.
- college_type: government (including aided) or private."""


def _enabled() -> bool:
    flag = os.environ.get("ARHATA_AI", "").lower()
    if flag in ("off", "0", "false"):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or flag in ("on", "1", "true"))


def extract_with_ai(clean_text: str) -> dict | None:
    """clean_text must already have ID-like numbers removed."""
    if not clean_text.strip() or not _enabled():
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic(timeout=12.0, max_retries=1)
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": clean_text}],
        )
        if response.stop_reason != "end_turn":
            return None
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            return None
        data = json.loads(text)
    except Exception:  # never let the optional AI pass break the page
        return None
    return _validate(data)


def _validate(data: dict) -> dict:
    out = {}
    out["education_level"] = data.get("education_level") if data.get("education_level") in LEVELS else None
    out["community"] = data.get("community") if data.get("community") in COMMUNITIES else None
    out["gender"] = data.get("gender") if data.get("gender") in ("female", "male", "other") else None
    out["area"] = data.get("area") if data.get("area") in ("rural", "urban") else None
    out["college_type"] = data.get("college_type") if data.get("college_type") in ("government", "private") else None
    year = data.get("year")
    out["year"] = year if isinstance(year, int) and 1 <= year <= 6 else None
    inc = data.get("annual_income")
    out["annual_income"] = inc if isinstance(inc, int) and 0 < inc < 10_000_000 else None
    marks = data.get("marks_percent")
    out["marks_percent"] = marks if isinstance(marks, (int, float)) and 0 < marks <= 100 else None
    dis = data.get("disability")
    out["disability"] = dis if isinstance(dis, bool) else None
    district = data.get("district")
    out["district"] = district.strip()[:40] if isinstance(district, str) and district.strip() else None
    return out
