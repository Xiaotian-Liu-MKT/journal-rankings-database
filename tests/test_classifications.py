import json
import re
import unittest

from journaldb.classifications import load_taxonomy
from journaldb.query import connect


class ClassificationCrosswalkTests(unittest.TestCase):
    def test_asset_integrity_and_scope_sensitive_categories(self):
        data = load_taxonomy()
        nodes = {node["id"]: node for node in data["nodes"]}
        self.assertEqual(len(nodes), len(data["nodes"]))
        for node in nodes.values():
            self.assertNotIn("\ufffd", node["label_en"] + node["label_zh"])
            parent = node["parent_id"]
            if parent:
                self.assertIn(parent, nodes)
                self.assertIsNone(nodes[parent]["parent_id"])
            if re.fullmatch(r"asjc-\d{4}", node["id"]):
                self.assertEqual(parent, "area-" + node["id"][5:7] + "00")
            for broader in node.get("refines", []):
                self.assertIn(broader, nodes)
                self.assertEqual(nodes[broader]["parent_id"], parent)
        for mapping in data["mappings"].values():
            for targets in mapping.values():
                self.assertTrue(targets)
                self.assertTrue(all(target in nodes for target in targets))
        self.assertEqual(nodes["asjc-1406"]["label_zh"], "市场营销")
        # Same-name fields can have different scope: WoS gerontology is not nursing.
        gerontology = data["mappings"]["WOS"]["GERONTOLOGY"]
        self.assertTrue(all(nodes[node]["parent_id"] == "area-3300" for node in gerontology))
        self.assertNotIn("asjc-2909", gerontology)
        pediatrics = data["mappings"]["WOS"]["PEDIATRICS"]
        self.assertTrue(all(nodes[node]["parent_id"] == "area-2700" for node in pediatrics))
        self.assertNotIn("asjc-2919", pediatrics)

    def test_current_source_labels_have_explicit_crosswalks(self):
        con = connect()
        data = load_taxonomy()
        try:
            for row in con.execute("SELECT s.system,s.metric_year,o.metrics FROM observations o JOIN sources s USING(source_id)"):
                system, year, raw = row
                metrics = json.loads(raw)
                if system in {"SJR", "AJG", "ABDC"}:
                    if year != (2024 if system == "AJG" else 2025):
                        continue
                    labels = [metrics.get("field")] if system != "SJR" else [re.sub(r"\s*\(Q[1-4]\)$", "", c) for c in metrics["categories"]]
                    target_system = system
                elif system == "JCR" or system in {"SCIE", "SSCI", "AHCI", "ESCI"}:
                    labels = [c["category"] if isinstance(c, dict) else c for c in metrics["categories"]]
                    target_system = "WOS"
                else:
                    continue
                for label in labels:
                    if label:
                        self.assertIn(label, data["mappings"][target_system], (system, label))
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
