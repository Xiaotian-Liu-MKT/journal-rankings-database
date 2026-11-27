import copy
import hashlib
import json
import unittest

from journaldb import DEFAULT_DB, ROOT
from journaldb.query import connect
from journaldb.special_issues import (
    DEFAULT_SPECIAL_ISSUES,
    load_special_issues,
    validate_special_issues,
)


class SpecialIssuesTests(unittest.TestCase):
    def test_special_issues_json_valid_and_covers_29_journals(self):
        data = load_special_issues(DEFAULT_SPECIAL_ISSUES)
        errors = validate_special_issues(data, db_path=DEFAULT_DB)
        self.assertEqual(errors, [], f"Validation errors: {errors}")

        journals = data["journals"]
        self.assertEqual(len(journals), 29)
        domain_counts = {}
        for j in journals:
            domain_counts[j["domain"]] = domain_counts.get(j["domain"], 0) + 1
        self.assertEqual(domain_counts, {"marketing": 11, "is": 11, "tourism": 7})

    def test_all_journal_ids_exist_in_sqlite_catalogue(self):
        data = load_special_issues(DEFAULT_SPECIAL_ISSUES)
        con = connect(DEFAULT_DB)
        try:
            db_ids = {row[0] for row in con.execute("SELECT journal_id FROM catalogue")}
        finally:
            con.close()
        for j in data["journals"]:
            self.assertIn(j["journal_id"], db_ids, f"Missing journal_id in SQLite: {j['journal_id']}")

    def test_validator_catches_invalid_entries(self):
        base = load_special_issues(DEFAULT_SPECIAL_ISSUES)

        bad_date = copy.deepcopy(base)
        bad_date["updated_at"] = "2026/11/27"
        self.assertTrue(validate_special_issues(bad_date, db_path=None))

        bad_id = copy.deepcopy(base)
        bad_id["journals"][0]["journal_id"] = "j_nonexistent000000"
        self.assertTrue(validate_special_issues(bad_id, db_path=DEFAULT_DB))

        bad_count = copy.deepcopy(base)
        bad_count["journals"][0]["open_count"] = bad_count["journals"][0]["open_count"] + 2
        self.assertTrue(validate_special_issues(bad_count, db_path=None))

        bad_status = copy.deepcopy(base)
        bad_status["journals"][0]["status"] = "ok_none" if bad_status["journals"][0]["open_count"] > 0 else "ok_open"
        self.assertTrue(validate_special_issues(bad_status, db_path=None))

        valid_with_issue = copy.deepcopy(base)
        j0 = valid_with_issue["journals"][0]
        j0["status"] = "ok_open"
        j0["open_count"] = j0["open_count"] + 1
        valid_with_issue["issues"].append({
            "id": "si_test_001",
            "journal_id": j0["journal_id"],
            "journal_title": j0["title"],
            "domain": j0["domain"],
            "title": "Test Special Issue",
            "summary_zh": "这是一个用于校验测试的中文主题概括。",
            "deadline_date": "2027-06-30",
            "deadline_raw": "30 June 2027",
            "deadline_type": "fixed",
            "guest_editors": ["Alice Smith"],
            "cfp_url": j0["cfp_url"],
            "checked_at": "2026-11-27",
        })
        self.assertEqual(validate_special_issues(valid_with_issue, db_path=DEFAULT_DB), [])

        bad_domain_mismatch = copy.deepcopy(valid_with_issue)
        other_domain = "tourism" if j0["domain"] != "tourism" else "marketing"
        bad_domain_mismatch["issues"][-1]["domain"] = other_domain
        self.assertTrue(validate_special_issues(bad_domain_mismatch, db_path=None))

    def test_static_export_includes_special_issues(self):
        assets = ROOT / "site" / "assets"
        manifest = json.loads((assets / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("special_issues"), "special-issues.json")
        exported_path = assets / manifest["special_issues"]
        self.assertTrue(exported_path.is_file())
        expected_hash = hashlib.sha256(exported_path.read_bytes()).hexdigest()[:12]
        self.assertEqual(manifest.get("special_issues_sha256"), expected_hash)
        self.assertTrue((ROOT / "site" / "special-issues.js").is_file())
        self.assertTrue((ROOT / "site" / "special-issues.css").is_file())
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn("special-issues.js?v=", html)
        self.assertIn("special-issues.css?v=", html)


if __name__ == "__main__":
    unittest.main()
