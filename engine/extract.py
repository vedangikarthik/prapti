"""Turn plain text into a student profile.

Step 3 ships the rule-based fallback parser (works offline, no AI).
Step 4 adds an LLM first pass; this parser stays as the fallback.

Guardrail: anything that looks like an ID number is removed before parsing.
"""
from __future__ import annotations

import re

PROFILE_KEYS = ["education_level", "year", "community", "annual_income", "gender", "area",
                "district", "disability", "marks_percent", "college_type"]

# 12-digit Aadhaar-like numbers (with optional spaces/dashes) and PAN-like codes.
_AADHAAR = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
_PAN = re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b")
_LONG_NUMBER = re.compile(r"(?<!\d)\d{10,}(?!\d)")

TELANGANA_DISTRICTS = [
    "Adilabad", "Bhadradri Kothagudem", "Hanumakonda", "Hyderabad", "Jagtial", "Jangaon",
    "Jayashankar Bhupalpally", "Jogulamba Gadwal", "Kamareddy", "Karimnagar", "Khammam",
    "Kumuram Bheem Asifabad", "Mahabubabad", "Mahabubnagar", "Mancherial", "Medak",
    "Medchal", "Mulugu", "Nagarkurnool", "Nalgonda", "Narayanpet", "Nirmal", "Nizamabad",
    "Peddapalli", "Rajanna Sircilla", "Rangareddy", "Sangareddy", "Siddipet", "Suryapet",
    "Vikarabad", "Wanaparthy", "Warangal", "Yadadri Bhuvanagiri",
]
DISTRICT_ALIASES = {
    "హైదరాబాద్": "Hyderabad", "हैदराबाद": "Hyderabad", "వరంగల్": "Warangal", "नलगोंडा": "Nalgonda",
    "నల్గొండ": "Nalgonda", "కరీంనగర్": "Karimnagar", "ఖమ్మం": "Khammam", "నిజామాబాద్": "Nizamabad",
    "secunderabad": "Hyderabad", "ranga reddy": "Rangareddy",
}
URBAN_DISTRICTS = {"Hyderabad", "Medchal", "Rangareddy"}


def scrub_ids(text: str) -> tuple[str, bool]:
    """Remove ID-like numbers. Returns (clean_text, removed_anything)."""
    cleaned = _AADHAAR.sub(" ", text)
    cleaned = _PAN.sub(" ", cleaned)
    cleaned = _LONG_NUMBER.sub(" ", cleaned)
    return cleaned, cleaned != text


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _income(t: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lac|l\b|లక్షలు|లక్ష|लाख)", t, re.I)
    if m:
        return int(_num(m.group(1)) * 100000)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:thousand|k\b|వేలు|వేల|हज़ार|हजार)", t, re.I)
    if m:
        return int(_num(m.group(1)) * 1000)
    # plain number near an income word, e.g. "income is 80,000"
    m = re.search(r"(?:income|earn\w*|salary|ఆదాయం|आय|आमदनी)\D{0,30}?(\d{1,3}(?:,\d{2,3})+|\d{4,7})", t, re.I)
    if m:
        return int(_num(m.group(1)))
    m = re.search(r"(\d{1,3}(?:,\d{2,3})+|\d{5,7})\s*(?:a year|per year|per annum|yearly|/year)", t, re.I)
    if m:
        return int(_num(m.group(1)))
    return None


def _community(t: str):
    if re.search(r"\bEBC\b", t, re.I):
        return "EBC"
    if re.search(r"\bS\.?C\.?\b|scheduled caste|దళిత", t, re.I):
        return "SC"
    if re.search(r"\bS\.?T\.?\b|scheduled tribe|tribal|గిరిజన|आदिवासी", t, re.I):
        return "ST"
    if re.search(r"\bBC(?:[\s-]?[A-E])?\b|backward|\bOBC\b|బీసీ", t, re.I):
        return "BC"
    if re.search(r"minorit|muslim|christian|sikh|మైనారిటీ|ముస్లిం|अल्पसंख्यक|मुस्लिम", t, re.I):
        return "Minority"
    if re.search(r"\bOC\b|\bgeneral\b|forward caste", t, re.I):
        return "OC"
    return None


def _education(t: str):
    checks = [
        ("pg", r"\b(?:m\.?\s?tech|mba|mca|m\.?\s?sc|m\.?\s?com|m\.?\s?a\b|post\s?grad\w*|\bpg\b|masters?)"),
        ("professional", r"b\.?\s?tech|\bbe\b|engineering|mbbs|b\.?\s?pharm|pharmacy|medical|bds|nursing|b\.?\s?arch|ఇంజనీరింగ్|इंजीनियरिंग"),
        ("iti_polytechnic", r"polytechnic|diploma|\biti\b|పాలిటెక్నిక్|पॉलिटेक्निक"),
        ("degree", r"\bdegree\b|b\.?\s?com|b\.?\s?sc|b\.?\s?a\b|\bbba\b|\bbca\b|graduat|డిగ్రీ|डिग्री"),
        ("inter", r"\binter\b|intermediate|junior college|\b1[12](?:th)?\s*(?:class|std)?\b|class\s*1[12]|ఇంటర్|इंटर"),
        ("class_10", r"class\s*10|10th\s*(?:class|std|standard)|\bin\s*10th|\bssc\b|పదవ తరగతి|दसवीं"),
        ("class_9", r"class\s*9|9th\s*(?:class|std|standard)|\bin\s*9th|తొమ్మిదవ తరగతి|नौवीं"),
    ]
    for level, pattern in checks:
        if re.search(pattern, t, re.I):
            return level
    return None


def _year(t: str):
    words = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "final": 4,
             "మొదటి": 1, "రెండవ": 2, "రెండో": 2, "మూడవ": 3, "నాలుగవ": 4, "पहले": 1, "पहला": 1, "दूसरे": 2, "दूसरा": 2, "तीसरे": 3}
    m = re.search(r"(first|1st|second|2nd|third|3rd|fourth|4th|final|మొదటి|రెండవ|రెండో|మూడవ|నాలుగవ|पहले|पहला|दूसरे|दूसरा|तीसरे)\s*(?:-|\s)?\s*(?:year|yr|సంవత్సరం|साल|वर्ष)", t, re.I)
    if m:
        return words[m.group(1).lower()]
    m = re.search(r"(?:year|yr)\s*(\d)", t, re.I)
    if m:
        return int(m.group(1))
    return None


def _gender(t: str):
    if re.search(r"\b(?:girl|female|daughter|woman|she|her)\b|विद्यार्थिनी|छात्रा|रही\s*(?:हूँ|हूं)|విద్యార్థిని|అమ్మాయి", t, re.I):
        return "female"
    if re.search(r"\b(?:boy|male|son|man|he|his)\b|छात्र\b|रहा\s*(?:हूँ|हूं)|అబ్బాయి", t, re.I):
        return "male"
    return None


def _district(t: str):
    for d in TELANGANA_DISTRICTS:
        if re.search(r"\b" + re.escape(d) + r"\b", t, re.I):
            return d
    for alias, d in DISTRICT_ALIASES.items():
        if alias.lower() in t.lower():
            return d
    return None


def _area(t: str, district):
    if re.search(r"village|rural|gram|గ్రామం|పల్లె|ఊరు|गाँव|गांव|ग्रामीण", t, re.I):
        return "rural"
    if re.search(r"\bcity\b|urban|\btown\b|शहर|నగరం|పట్టణం", t, re.I):
        return "urban"
    if district in URBAN_DISTRICTS:
        return "urban"
    return None


def _disability(t: str):
    if re.search(r"disab|handicap|\bpwd\b|divyang|blind|deaf|wheelchair|వికలాంగ|దివ్యాంగ|दिव्यांग|विकलांग", t, re.I):
        if re.search(r"\bno\s+disab|not\s+disabled", t, re.I):
            return False
        return True
    return None


def _marks(t: str):
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*(?:%|percent|per cent|శాతం|प्रतिशत)", t, re.I)
    if m:
        v = _num(m.group(1))
        if 0 < v <= 100:
            return v
    return None


def _college(t: str):
    if re.search(r"government|govt|aided|zphs|zilla parishad|ప్రభుత్వ|सरकारी", t, re.I):
        return "government"
    if re.search(r"private|ప్రైవేట్|प्राइवेट|निजी", t, re.I):
        return "private"
    return None


def extract_fallback(text: str) -> dict:
    t = text or ""
    district = _district(t)
    return {
        "education_level": _education(t),
        "year": _year(t),
        "community": _community(t),
        "annual_income": _income(t),
        "gender": _gender(t),
        "area": _area(t, district),
        "district": district,
        "disability": _disability(t),
        "marks_percent": _marks(t),
        "college_type": _college(t),
    }


def extract(text: str) -> dict:
    """Returns {"profile": {...}, "removed_id": bool}."""
    clean, removed = scrub_ids(text or "")
    profile = extract_fallback(clean)
    return {"profile": profile, "removed_id": removed}
