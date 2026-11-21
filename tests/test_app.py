import os
import unittest

os.environ["ARHATA_AI"] = "off"  # tests never call the API

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

    def test_calendar_file(self):
        r = self.c.get("/api/ics/aicte-pragati")
        self.assertEqual(r.status_code, 200)
        self.assertIn("BEGIN:VCALENDAR", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
