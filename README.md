# Prapti (ప్రాప్తి · प्राप्ति) — receive what's yours

**ACE Builders Hackathon 2026 · Problem Statement 5: Claim What's Yours**

*Prapti* (ప్రాప్తి in Telugu, प्राप्ति in Hindi) means "receiving what is due to you". A student from a low-income family in Telangana describes their life in plain words (typed or spoken, in English, Telugu or Hindi). Prapti shows which government scholarships they are **likely eligible** for, the exact rule behind every match, a personal document checklist, the steps on the official portal, and reminders before each last date.

## Who it is for

Students from Class 9 to PG in Telangana whose families earn under about ₹8 lakh a year, and the people who help them: parents, teachers, NGO volunteers and Mee Seva operators.

## What it does

| Requirement in the brief | Where it is in Prapti |
|---|---|
| Plain-language input, typed or spoken, regional language | Home page text box with voice input (te-IN / hi-IN / en-IN); offline reader for English, Telugu and Hindi; optional Claude reading when an API key is set |
| Matching that shows its reasoning | A plain rules engine (`engine/match.py`). Every result lists each rule as a sentence with the student's own answer: "Family income up to ₹1,50,000 a year (rural), you said about ₹1,10,000" |
| Help for people who don't know which details matter | Quick questions ask only for missing details that would change a result, one tap each, with "why we ask" |
| Personal document checklist and step-by-step guide | Scheme page: checklist (only the certificates this student needs, with where to get them), portal steps, what happens after applying |
| Deadline reminders and tracking | My tracker: status from Not started to Received, days left, next step, browser reminders 14/7/3/1 days before, calendar file with alarms |
| Official source and last-verified date | Every scheme links to its official portal and shows "Last verified"; the editor flags any scheme not checked for 90 days |

### Guardrails

- Says **"likely eligible"**, never promises an outcome. A test scans every page for banned phrases.
- **No ID numbers.** Aadhaar-, PAN- and phone-like numbers are removed before anything reads the message, and the page says so.
- **Rules are data.** All limits live in `data/schemes.json`. The password-protected scheme editor (`/admin/schemes`) changes a limit with no code change and logs it in `data/changelog.json`.
- **Public information only**, sample students only.
- The tracker, checklist and helper list are saved on the user's own device (localStorage). There are no accounts.

## Who pays

Prapti is free for students and replaces middlemen who charge ₹500–2,000 per application. CSR funds sponsor districts and get an outcome report. NGOs and Mee Seva centres use **Helper mode** (`/helper`): one student after another under nicknames, impact counts, and a printable checklist for students without phones. Banks pay referral fees on loan schemes only, never ranked above free schemes. State and district governments can run it as a pilot. Full table on `/about`.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py            # http://127.0.0.1:5050
```

Port 5050 is the default because macOS AirPlay uses 5000. Set `PORT` to change it.

Optional settings:

| Variable | What it does |
|---|---|
| `ANTHROPIC_API_KEY` | Turns on AI reading of the student's message (Claude, structured JSON, low effort). Without it the offline reader is used. `PRAPTI_AI=off` forces offline. |
| `ADMIN_PASSWORD` | Password for the scheme editor. The demo default is `prapti-demo`; change it before any public use. |
| `SECRET_KEY` | Signs the session cookie. Set a long random value in production. |

Run the tests:

```bash
PRAPTI_AI=off python -m unittest discover -s tests -t .
```

## How it is built

```
app.py                 Flask routes: home, questions, results, scheme, tracker, helper, about, editor, JSON API
engine/extract.py      Text → profile: ID scrubber + offline English/Telugu/Hindi reader
engine/llm.py          Optional Claude reading (never decides eligibility)
engine/match.py        Rules engine: likely / might be / not a match, with reasons
engine/ics.py          Calendar file with reminders
data/schemes.json      10 schemes, rules, documents, steps, sources, verification notes
data/i18n.json         Every screen's text in English, Telugu and Hindi
data/samples.json      Lakshmi, Ravi, Ayesha (sample students)
templates/, static/    Screens, styles (tokens.css + app.css), scripts
tests/                 27 tests: matching, reading, flow, languages, editor, guardrails
```

API: `POST /api/extract`, `POST /api/match`, `GET /api/scheme/<id>`, `GET /api/ics/<id>`, `POST /api/helper-check`.

## Schemes covered

Telangana ePASS Post-Matric (SC/ST, BC/EBC, Minorities), Reimbursement of Tuition Fee, Pre-Matric (Class 9–10); NMMS; Central Sector Scholarship; AICTE Pragati; AICTE Saksham; PM-Vidyalaxmi education loan. Limits, amounts and dates were checked against public sources on 21 Nov 2026. Each scheme carries a `verification` note with its sources and confidence. The Pre-Matric income limit is not yet confirmed and is shown as not verified.

## Honest limits

- Telugu and Hindi interface text is a first draft and should be reviewed by native speakers. Scheme documents and steps are shown in English, as on the official portals.
- ePASS figures come from 2026-27 guides because the official notices could not be read online; confirm on telanganaepass.cgg.gov.in.
- Thresholds like "top 20% of the Class 12 board" are approximated (80% marks).

## Credits

Photographs from Wikimedia Commons: Kakatiya torana at Warangal Fort by Ms Sarah Welch (CC0); Department of Telugu classroom, Osmania University by Myadam Abhilash (CC0); Osmania University Arts College corridor and window by iMahesh (CC BY-SA 4.0). Typefaces: Young Serif, Source Serif 4, Noto Serif Telugu, Noto Serif Devanagari (Google Fonts, OFL).

*Prapti is a free guide, not a government website. Final eligibility is decided by the scheme authority. Never pay anyone to apply.*
