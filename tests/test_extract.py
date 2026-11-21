import unittest

from engine.extract import extract, scrub_ids


class TestExtract(unittest.TestCase):
    def test_english(self):
        p = extract("I'm in Inter 2nd year in Warangal, we are BC, income around 1 lakh, got 72% in 10th")["profile"]
        self.assertEqual(p["education_level"], "inter")
        self.assertEqual(p["year"], 2)
        self.assertEqual(p["community"], "BC")
        self.assertEqual(p["annual_income"], 100000)
        self.assertEqual(p["district"], "Warangal")
        self.assertEqual(p["marks_percent"], 72)

    def test_telugu(self):
        p = extract("నేను డిగ్రీ మొదటి సంవత్సరం, మా ఊరు నల్గొండ, మేము SC, మా ఆదాయం 80 వేలు.")["profile"]
        self.assertEqual(p["education_level"], "degree")
        self.assertEqual(p["year"], 1)
        self.assertEqual(p["community"], "SC")
        self.assertEqual(p["annual_income"], 80000)
        self.assertEqual(p["area"], "rural")
        self.assertEqual(p["district"], "Nalgonda")

    def test_hindi(self):
        p = extract("मैं हैदराबाद में B.Tech कर रही हूँ, हम minority हैं, family income 1.5 लाख है।")["profile"]
        self.assertEqual(p["education_level"], "professional")
        self.assertEqual(p["community"], "Minority")
        self.assertEqual(p["annual_income"], 150000)
        self.assertEqual(p["gender"], "female")
        self.assertEqual(p["area"], "urban")

    def test_unknown_stays_none(self):
        p = extract("hello")["profile"]
        self.assertTrue(all(v is None for v in p.values()))

    def test_id_numbers_removed(self):
        r = extract("my aadhaar is 1234 5678 9012 and PAN ABCDE1234F, inter BC 1 lakh")
        self.assertTrue(r["removed_id"])
        clean, removed = scrub_ids("call 9876543210")
        self.assertTrue(removed)
        self.assertNotIn("9876543210", clean)
        self.assertEqual(r["profile"]["community"], "BC")


if __name__ == "__main__":
    unittest.main()
