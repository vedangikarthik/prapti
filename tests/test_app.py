import os
import unittest

os.environ["PRAPTI_AI"] = "off"  # tests never call the API

try:
    from app import app
except ImportError:  # Flask not installed in this interpreter
    app = None

BANNED = ("guaranteed", "you will get", "you are approved", "confirmed eligible")


@unittest.skipIf(app is None, "Flask not installed")
class TestFlow(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.c = app.test_client()

    def test_sample_goes_straight_to_results(self):
        r = self.c.post("/find", data={"sample": "lakshmi"})
        self.assertTrue(r.headers["Location"].endswith("/results"))
        page = self.c.get("/results").get_data(as_text=True)
        self.assertIn("Lakshmi is likely eligible for 2 schemes", page)

    def test_text_with_gaps_asks_only_what_matters(self):
        r = self.c.post("/find", data={"text": "I am in B.Tech 1st year, we are SC, family income 80,000 a year"})
        self.assertTrue(r.headers["Location"].endswith("/questions"))
        page = self.c.get("/questions").get_data(as_text=True)
        self.assertIn("Are you a girl or a boy?", page)
        self.assertNotIn("Which community", page)  # already known

    def test_answering_and_skipping_reach_results(self):
        self.c.post("/find", data={"text": "I am in B.Tech 1st year, we are SC, family income 80,000 a year"})
        for _ in range(10):
            r = self.c.get("/questions")
            if r.status_code == 302:
                break
            page = r.get_data(as_text=True)
            field = page.split('name="field" value="')[1].split('"')[0]
            self.c.post("/questions", data={"field": field, "skip": "1"})
        self.assertTrue(r.headers["Location"].endswith("/results"))
        page = self.c.get("/results").get_data(as_text=True)
        self.assertIn("Post-Matric Scholarship (SC / ST)", page)

    def test_id_number_is_removed_and_noted(self):
        self.c.post("/find", data={"text": "aadhaar 1234 5678 9012, inter 2nd year BC 1 lakh village"})
        page = self.c.get("/questions").get_data(as_text=True)
        if "We removed a number" not in page:
            page = self.c.get("/results").get_data(as_text=True)
        self.assertIn("We removed a number", page)
        self.assertNotIn("1234 5678 9012", page)

    def test_no_banned_words_on_any_page(self):
        self.c.post("/find", data={"sample": "ravi"})
        for url in ["/", "/results", "/scheme/central-sector", "/scheme/aicte-pragati"]:
            page = self.c.get(url).get_data(as_text=True).lower()
            for word in BANNED:
                self.assertNotIn(word, page, url)

    def test_tracker_page(self):
        r = self.c.get("/tracker")
        self.assertEqual(r.status_code, 200)
        page = r.get_data(as_text=True)
        self.assertIn('id="schemes-meta"', page)
        self.assertIn("aicte-pragati", page)
        self.assertIn('href="/tracker"', self.c.get("/").get_data(as_text=True))

    def test_telugu_and_hindi(self):
        self.c.get("/lang/te")
        page = self.c.get("/").get_data(as_text=True)
        self.assertIn('<html lang="te">', page)
        self.assertIn("మీరు పొందగల స్కాలర్‌షిప్‌లు", page)
        self.c.post("/find", data={"sample": "lakshmi"})
        page = self.c.get("/results").get_data(as_text=True)
        self.assertIn("లక్ష్మి", page)
        self.assertIn("సంవత్సరానికి ₹1,10,000", page)
        self.c.get("/lang/hi")
        page = self.c.get("/scheme/ts-postmatric-bc-ebc").get_data(as_text=True)
        self.assertIn("पारिवारिक आय", page)
        self.assertIn("मेरे ट्रैकर में जोड़ें", page)
        self.c.get("/lang/en")

    def test_every_text_has_all_languages(self):
        import json
        with open("data/i18n.json", encoding="utf-8") as f:
            data = json.load(f)
        for key, entry in data.items():
            if key.startswith("_"):
                continue
            for lang in ("en", "te", "hi"):
                self.assertIn(lang, entry, key)

    def test_about_helper_and_print(self):
        self.assertIn("Who pays", self.c.get("/about").get_data(as_text=True))
        self.assertEqual(self.c.get("/helper").status_code, 200)
        r = self.c.post("/api/helper-check", json={"text": "Inter 2nd year BC 1 lakh village, aadhaar 1234 5678 9012"})
        d = r.get_json()
        self.assertTrue(d["removed_id"])
        self.assertIn("ts-postmatric-bc-ebc", [x["id"] for x in d["likely"]])
        page = self.c.get("/helper/print?nick=Student%201&ids=ts-rtf").get_data(as_text=True)
        self.assertIn("Documents to bring", page)

    def test_editor_needs_password_and_changes_results(self):
        import shutil, tempfile
        from engine import match
        backup = tempfile.mktemp()
        shutil.copy(match.SCHEMES_PATH, backup)
        from pathlib import Path
        log_backup = Path("data/changelog.json").read_text(encoding="utf-8")
        try:
            self.assertNotIn("admin-item", self.c.get("/admin/schemes").get_data(as_text=True))
            self.assertEqual(self.c.post("/admin/login", data={"password": "wrong"}).status_code, 401)
            self.c.post("/admin/login", data={"password": "prapti-demo"})
            form = self.c.get("/admin/schemes/ts-postmatric-bc-ebc").get_data(as_text=True)
            self.assertIn("Save and mark verified today", form)
            data = {"benefit_text": "x", "benefit_max_inr": "15000", "deadline": "2026-12-31", "deadline_note": "n",
                    "source_url": "https://telanganaepass.cgg.gov.in"}
            rules = match.load_schemes()
            sch = next(s for s in rules if s["id"] == "ts-postmatric-bc-ebc")
            for i, rule in enumerate(sch["rules"]):
                data[f"field_{i}"] = rule["field"]
                data[f"op_{i}"] = rule["op"]
                v = rule["value"]
                data[f"value_{i}"] = ", ".join(v) if isinstance(v, list) else str(v)
                data[f"text_{i}"] = rule["text_en"]
            data["value_2"] = "100000"  # rural limit below Lakshmi's ₹1.1L
            r = self.c.post("/admin/schemes/ts-postmatric-bc-ebc", data=data)
            self.assertEqual(r.status_code, 302)
            self.c.post("/find", data={"sample": "lakshmi"})
            page = self.c.get("/results").get_data(as_text=True)
            self.assertIn("1 scheme", page)
        finally:
            shutil.copy(backup, match.SCHEMES_PATH)
            Path("data/changelog.json").write_text(log_backup, encoding="utf-8")
            self.c.post("/admin/logout")

    def test_tap_only_path_and_back(self):
        r = self.c.post("/start")
        self.assertTrue(r.headers["Location"].endswith("/questions"))
        page = self.c.get("/questions").get_data(as_text=True)
        self.assertIn("What are you studying now?", page)
        self.c.post("/questions", data={"field": "education_level", "value": "degree"})
        page = self.c.get("/questions").get_data(as_text=True)
        self.assertIn("/questions/back", page)
        current = page.split('name="current" value="')[1].split('"')[0]
        self.c.post("/questions/back", data={"current": current})
        self.assertIn("What are you studying now?", self.c.get("/questions").get_data(as_text=True))

    def test_results_show_first_step_and_listen(self):
        self.c.post("/find", data={"sample": "lakshmi"})
        page = self.c.get("/results").get_data(as_text=True)
        self.assertIn("Your first step", page)
        self.assertIn("Show me how to apply", page)
        self.assertIn("data-speak", page)
        self.assertIn('id="how"', self.c.get("/scheme/ts-rtf").get_data(as_text=True))

    def test_first_visit_language_choice(self):
        fresh = app.test_client()
        self.assertIn('class="lang-pick"', fresh.get("/").get_data(as_text=True))
        fresh.get("/lang/te")
        self.assertNotIn('class="lang-pick"', fresh.get("/").get_data(as_text=True))

    def test_calendar_file(self):
        r = self.c.get("/api/ics/aicte-pragati")
        self.assertEqual(r.status_code, 200)
        self.assertIn("BEGIN:VCALENDAR", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
