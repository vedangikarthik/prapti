import copy
import json
import os
import re
import tempfile
import unittest
from datetime import date

from engine.match import (SCHEMES_PATH, DATA_DIR, fields_that_matter, load_schemes,
                          match_all, match_scheme)

BANNED = re.compile(r"guarantee|you will get|you are approved|confirmed eligible", re.I)


def load_samples():
    with open(os.path.join(DATA_DIR, "samples.json"), encoding="utf-8") as f:
        return json.load(f)["samples"]


class TestSampleStudents(unittest.TestCase):
    def setUp(self):
        self.schemes = load_schemes()
        self.samples = {s["id"]: s for s in load_samples()}

    def test_each_sample_gets_expected_likely_schemes(self):
        for sid, sample in self.samples.items():
            with self.subTest(student=sid):
                result = match_all(sample["profile"], self.schemes)
                got = sorted(r["id"] for r in result["likely"])
                self.assertEqual(got, sorted(sample["expected_likely"]))
                self.assertEqual(result["maybe"], [])

    def test_failed_rule_is_explained(self):
        lakshmi = self.samples["lakshmi"]["profile"]
        sc_st = next(s for s in self.schemes if s["id"] == "ts-postmatric-sc-st")
        r = match_scheme(sc_st, lakshmi)
        self.assertEqual(r["status"], "no")
        self.assertIn("you said BC", r["failed"][0]["text"])

    def test_reason_text_uses_student_value(self):
        ravi = self.samples["ravi"]["profile"]
        sc_st = next(s for s in self.schemes if s["id"] == "ts-postmatric-sc-st")
        texts = " ".join(r["text"] for r in match_scheme(sc_st, ravi)["reasons"])
        self.assertIn("₹80,000", texts)
        self.assertNotIn("{user_value}", texts)

    def test_loans_not_counted_in_value(self):
        result = match_all(self.samples["ravi"]["profile"], self.schemes)
        free = sum(r["benefit_max_inr"] for r in result["likely"] if r["category"] != "loan")
        self.assertEqual(result["summary"]["likely_value_inr"], free)


class TestMissingDetails(unittest.TestCase):
    def setUp(self):
        self.schemes = load_schemes()
        self.lakshmi = copy.deepcopy(load_samples()[0]["profile"])

    def test_missing_area_gives_maybe(self):
        self.lakshmi["area"] = None
        result = match_all(self.lakshmi, self.schemes)
        maybe_ids = [r["id"] for r in result["maybe"]]
        self.assertIn("ts-postmatric-bc-ebc", maybe_ids)
        bc = next(r for r in result["maybe"] if r["id"] == "ts-postmatric-bc-ebc")
        self.assertIn("area", bc["missing_fields"])

    def test_missing_income_gives_maybe_not_no(self):
        self.lakshmi.pop("annual_income")
        result = match_all(self.lakshmi, self.schemes)
        self.assertIn("ts-postmatric-bc-ebc", [r["id"] for r in result["maybe"]])
        self.assertIn("annual_income", fields_that_matter(self.lakshmi, self.schemes))

    def test_empty_profile_never_crashes(self):
        result = match_all({}, self.schemes)
        self.assertEqual(len(result["likely"]) + len(result["maybe"]) + len(result["no"]), len(self.schemes))


class TestRulesAreData(unittest.TestCase):
    def test_changing_json_changes_result_without_code_change(self):
        lakshmi = load_samples()[0]["profile"]
        with open(SCHEMES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for s in data["schemes"]:
            if s["id"] == "ts-postmatric-bc-ebc":
                for rule in s["rules"]:
                    if rule["field"] == "annual_income":
                        rule["value"] = 100000  # lower the limit below Lakshmi's ₹1.1L
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "schemes.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            result = match_all(lakshmi, load_schemes(path))
        self.assertIn("ts-postmatric-bc-ebc", [r["id"] for r in result["no"]])


class TestGuardrailsInData(unittest.TestCase):
    def test_every_scheme_has_source_and_fields(self):
        required = {"id", "name_en", "name_te", "name_hi", "run_by", "category", "summary_en", "benefit_text",
                    "benefit_max_inr", "rules", "documents", "steps", "after_apply", "deadline", "deadline_note",
                    "source_name", "source_url", "last_verified"}
        for s in load_schemes():
            with self.subTest(scheme=s["id"]):
                self.assertTrue(required <= set(s), required - set(s))
                self.assertTrue(s["source_url"].startswith("https://"))
                for rule in s["rules"]:
                    self.assertIn(rule["op"], {"eq", "in", "lte", "gte", "lt", "gt"})
                    for lang in ("en", "te", "hi"):
                        self.assertIn("{user_value}", rule[f"text_{lang}"])

    def test_no_banned_words_in_data(self):
        for name in ("schemes.json", "samples.json"):
            with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
                self.assertIsNone(BANNED.search(f.read()), name)

    def test_days_left(self):
        s = next(s for s in load_schemes() if s["deadline"])
        r = match_scheme(s, {}, today=date.fromisoformat(s["deadline"]))
        self.assertEqual(r["days_left"], 0)


if __name__ == "__main__":
    unittest.main()
