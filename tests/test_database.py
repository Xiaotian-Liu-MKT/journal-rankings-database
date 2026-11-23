import csv
import json
import sqlite3
import unittest
from pathlib import Path

from journaldb import ROOT, DEFAULT_DB
from journaldb.build import issn, norm
from journaldb.query import connect, detail, filters, meta, search


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.con = connect()

    def tearDown(self):
        self.con.close()

    def test_source_record_conservation(self):
        for source in self.con.execute("SELECT * FROM sources"):
            actual = self.con.execute("SELECT count(*) FROM observations WHERE source_id=?", (source["source_id"],)).fetchone()[0]
            self.assertEqual(source["row_count"], actual, source["source_id"])
        self.assertEqual(self.con.execute("SELECT sum(row_count) FROM sources").fetchone()[0], self.con.execute("SELECT count(*) FROM observations").fetchone()[0])
        for filename, delimiter in (("2025 Journal Impact Factor.txt", ","), ("scimagojr 2025.csv", ";"), ("FT50.txt", ","), ("UTD24.txt", ",")):
            with (ROOT / filename).open(encoding="utf-8-sig", newline="") as f:
                expected = len(list(csv.reader(f, delimiter=delimiter))) - 1
            actual = self.con.execute("SELECT sum(row_count) FROM sources WHERE filename=?", (filename,)).fetchone()[0]
            self.assertEqual(expected, actual)
        for filename in ("SCIE.csv", "SSCI.csv", "AHCI.csv", "ESCI.csv"):
            with (ROOT / filename).open(encoding="utf-8-sig", newline="") as f:
                expected = len(list(csv.reader(f))) - 1
            source = self.con.execute("SELECT * FROM sources WHERE filename=?", (filename,)).fetchone()
            self.assertIsNotNone(source)
            self.assertEqual((source["system"], source["edition"], source["metric_year"], source["row_count"]),
                             (Path(filename).stem, "undated", None, expected))
        self.assertEqual(self.con.execute("SELECT count(*) FROM sources WHERE duplicate_of IS NOT NULL").fetchone()[0], 1)

    def test_integrity_and_read_only(self):
        self.assertEqual(self.con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertFalse(self.con.execute("PRAGMA foreign_key_check").fetchall())
        with self.assertRaises(sqlite3.OperationalError):
            self.con.execute("DELETE FROM metadata")

    def test_issn_check_digit_and_normalization(self):
        self.assertEqual(issn(" 00935301\t"), "0093-5301")
        self.assertEqual(issn("2445-4192\u200e"), "2445-4192")
        self.assertIsNone(issn("0093-5302"))
        self.assertIsNone(issn("N/A"))
        self.assertEqual(norm("The Accounting, Auditing & Accountability Journal"), norm("Accounting Auditing and Accountability Journal"))

    def test_exact_title_first_and_issn(self):
        result = search(self.con, q="Journal of Consumer Research")
        journal = result["results"][0]
        self.assertEqual(norm(journal["title"]), "journal of consumer research")
        ids = {r["journal_id"] for r in search(self.con, q="00935301")["results"]}
        self.assertIn(journal["journal_id"], ids)
        self.assertEqual((journal["abdc"], journal["ajg"], journal["ft50"], journal["utd24"]), ("A*", "4*", True, True))

    def test_current_abdc_never_backfills(self):
        wrong = self.con.execute("""SELECT count(*) FROM catalogue c WHERE c.abdc IS NOT NULL
          AND NOT EXISTS(SELECT 1 FROM observations o JOIN sources s USING(source_id)
          WHERE o.journal_id=c.journal_id AND s.system='ABDC' AND s.edition='2025'
            AND json_extract(o.metrics,'$.rating')=c.abdc)""").fetchone()[0]
        self.assertEqual(wrong, 0)
        old_only = self.con.execute("""SELECT count(*) FROM catalogue c WHERE c.abdc IS NULL
          AND EXISTS(SELECT 1 FROM observations o JOIN sources s USING(source_id)
          WHERE o.journal_id=c.journal_id AND s.system='ABDC' AND s.metric_year<2025)""").fetchone()[0]
        self.assertGreater(old_only, 0)

    def test_membership_and_combinations(self):
        stats = meta(self.con)["stats"]
        self.assertEqual((stats["ft50"], stats["utd24"]), (50, 24))
        results = search(self.con, abdc="A*", ajg="4*", utd24="1", ft50="1")
        self.assertGreater(results["total"], 10)
        for item in results["results"]:
            self.assertEqual((item["abdc"], item["ajg"], item["ft50"], item["utd24"]), ("A*", "4*", True, True))

    def test_jcr_all_categories_and_sjr_decimal(self):
        journal = search(self.con, q="CA-A CANCER JOURNAL FOR CLINICIANS")["results"][0]
        self.assertEqual(journal["sjr"], 104.065)
        self.assertEqual(journal["impact_factor"], 685.2)
        journal = search(self.con, q="World Psychiatry")["results"][0]
        original = detail(self.con, journal["journal_id"])
        jcr = next(r for r in original["observations"] if r["system"] == "JCR")
        self.assertTrue(jcr["metrics"]["categories"][0]["rank"])
        multi = self.con.execute("SELECT journal_id FROM observations JOIN sources USING(source_id) WHERE system='JCR' AND json_array_length(metrics,'$.categories')>1 LIMIT 1").fetchone()[0]
        self.assertTrue(any(len(o["metrics"].get("categories", [])) > 1 for o in detail(self.con, multi)["observations"] if o["system"] == "JCR"))

    def test_wos_indexes_preserve_rows_and_support_filtering(self):
        stats = meta(self.con)["stats"]
        self.assertEqual(set(stats["wos_index_counts"]), {"SCIE", "SSCI", "AHCI", "ESCI"})
        self.assertTrue(all(count > 0 for count in stats["wos_index_counts"].values()))
        overlap = self.con.execute("SELECT journal_id FROM catalogue WHERE json_array_length(wos_indexes) > 1 LIMIT 1").fetchone()
        self.assertIsNotNone(overlap)
        journal = detail(self.con, overlap["journal_id"])
        self.assertGreater(len(journal["journal"]["wos_indexes"]), 1)
        self.assertIsInstance(journal["journal"]["languages"], list)
        for index in journal["journal"]["wos_indexes"]:
            filtered = search(self.con, q=journal["journal"]["title"], wos_index=index, limit=500)
            self.assertIn(journal["journal"]["journal_id"], {row["journal_id"] for row in filtered["results"]})
        wos = next(row for row in journal["observations"] if row["system"] in {"SCIE", "SSCI", "AHCI", "ESCI"})
        self.assertEqual(wos["edition"], "undated")
        self.assertIsNone(wos["metric_year"])
        self.assertEqual(wos["system"], wos["metrics"]["index"])
        self.assertIn("Publisher name", wos["raw"])
        self.assertEqual(wos["metrics"]["publisher"], wos["raw"]["Publisher name"].strip())
        self.assertIsInstance(wos["metrics"]["languages"], list)
        self.assertIsInstance(wos["metrics"]["categories"], list)
        supplied_issns = {issn(wos["raw"][key]) for key in ("ISSN", "eISSN")} - {None}
        self.assertTrue(supplied_issns & set(journal["journal"]["issns"]))

    def test_types_pagination_and_numeric_filters(self):
        page1 = search(self.con, source_type="journal", min_if="5", sort="impact_factor", order="desc", limit=5)
        page2 = search(self.con, source_type="journal", min_if="5", sort="impact_factor", order="desc", limit=5, offset=5)
        self.assertFalse({r["journal_id"] for r in page1["results"]} & {r["journal_id"] for r in page2["results"]})
        self.assertTrue(all(r["impact_factor"] >= 5 and r["source_type"] == "journal" for r in page1["results"]))
        self.assertGreater(search(self.con, source_type="book series")["total"], 0)

    def test_query_validation_and_literal_safety(self):
        for params in ({"sort": "title; DROP TABLE journals"}, {"limit": 0}, {"offset": -1}, {"min_if": "NaN"}, {"abdc": "D"}, {"wos_index": "JCR"}):
            with self.assertRaises(ValueError):
                search(self.con, **params)
        search(self.con, q="' OR 1=1 --")
        self.assertEqual(search(self.con, q="%_%")["total"], 0)
        self.assertIsNone(detail(self.con, "no-such-id"))

    def test_bridged_identity_and_raw_preservation(self):
        matches = search(self.con, q="0951-3574")
        self.assertEqual(matches["total"], 1)
        original = detail(self.con, matches["results"][0]["journal_id"])
        systems = {r["system"] for r in original["observations"]}
        self.assertTrue({"JCR", "SJR", "ABDC", "AJG"} <= systems)
        sjr = next(r for r in original["observations"] if r["system"] == "SJR")
        self.assertIn("Publisher__2", sjr["raw"])

    def test_exports_have_same_entities_and_nulls(self):
        with (DEFAULT_DB.parent / "journals.csv").open(encoding="utf-8-sig", newline="") as f:
            count_csv = sum(1 for _ in csv.DictReader(f))
        with (DEFAULT_DB.parent / "journals.jsonl").open(encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        self.assertEqual(count_csv, meta(self.con)["stats"]["journals"])
        self.assertEqual(len(rows), count_csv)
        self.assertIsInstance(rows[0]["issns"], list)
        self.assertTrue(any(r["impact_factor"] is None for r in rows))


if __name__ == "__main__":
    unittest.main()
