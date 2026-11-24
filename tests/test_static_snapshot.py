import gzip
import hashlib
import json
import unittest

from journaldb import ROOT
from journaldb.query import connect, meta
from journaldb.acronyms import title_acronyms


class StaticSnapshotTests(unittest.TestCase):
    def test_complete_and_consistent_snapshot(self):
        base = ROOT / "site" / "assets"
        manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        records = json.loads(gzip.decompress((base / manifest["catalogue"]).read_bytes()))
        self.assertEqual(manifest["catalogue_sha256"], hashlib.sha256((base / manifest["catalogue"]).read_bytes()).hexdigest()[:12])
        entities = {dict(zip(manifest["columns"], row))["journal_id"] for row in records}
        con = connect()
        try:
            database_paths = {row["journal_id"]: json.loads(row["taxonomy_paths"]) for row in con.execute("SELECT journal_id,taxonomy_paths FROM catalogue")}
            self.assertEqual(manifest["taxonomy"], meta(con)["taxonomy"])
            expected_acronyms = {}
            for row in con.execute("SELECT journal_id, title FROM aliases"):
                expected_acronyms.setdefault(row["journal_id"], set()).update(title_acronyms(row["title"]))
            for row in records:
                record = dict(zip(manifest["columns"], row))
                self.assertEqual(set(record["search_acronyms"]), expected_acronyms[record["journal_id"]])
                self.assertEqual(record["taxonomy_paths"], database_paths[record["journal_id"]])
            self.assertEqual(len(records), meta(con)["stats"]["journals"])
            self.assertEqual(manifest["built_at"], meta(con)["built_at"])
            ids, count = set(), 0
            shards = list((base / "details").glob("*.json.gz"))
            self.assertEqual(len(shards), 256)
            for shard in shards:
                content = json.loads(gzip.decompress(shard.read_bytes()))
                for jid, record in content.items():
                    self.assertEqual(shard.name[:2], jid[2:4])
                    self.assertEqual(record["journal"]["journal_id"], jid)
                    self.assertTrue(record["observations"])
                    self.assertNotIn(jid, ids)
                    ids.add(jid)
                    count += len(record["observations"])
            self.assertEqual(ids, entities)
            self.assertEqual(count, meta(con)["stats"]["records"])
        finally:
            con.close()

    def test_only_static_files_and_relative_adapter(self):
        root = ROOT / "site"
        html = (root / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index("window.JOURNAL_STATIC=true"), html.index('src="static-client.js'))
        self.assertTrue((root / "static-client.js").is_file())
        self.assertTrue((root / ".nojekyll").exists())
        self.assertFalse(list(root.rglob("*.sqlite")))
        self.assertTrue(all(p.stat().st_size < 90_000_000 for p in root.rglob("*") if p.is_file()))


if __name__ == "__main__":
    unittest.main()
