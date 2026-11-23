"""Build a self-contained GitHub Pages snapshot from the canonical SQLite DB."""
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from . import ROOT, DEFAULT_DB
from .build import dumps
from .query import connect, decode, meta


def write_gzip(path, obj):
    data = dumps(obj).encode("utf-8")
    path.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))


def export_site(database=DEFAULT_DB, destination=None):
    output = Path(destination or ROOT / "site")
    assets = output / "assets"
    details_dir = assets / "details"
    details_dir.mkdir(parents=True, exist_ok=True)
    con = connect(database)
    try:
        metadata = meta(con)
        aliases = defaultdict(list)
        normalized = defaultdict(set)
        for row in con.execute("SELECT * FROM aliases ORDER BY title"):
            aliases[row["journal_id"]].append(row["title"])
            normalized[row["journal_id"]].add(row["normalized_title"])
        entities = {}
        columns, rows = None, []
        for row in con.execute("SELECT * FROM catalogue ORDER BY title COLLATE NOCASE,journal_id"):
            obj = decode(row)
            jid = obj["journal_id"]
            obj["normalized_aliases"] = sorted(normalized[jid])
            if columns is None:
                columns = list(obj)
            rows.append([obj[k] for k in columns])
            entities[jid] = {k: v for k, v in obj.items() if k not in ("search_text", "normalized_aliases")}
        write_gzip(assets / "catalogue.json.gz", rows)
        shards = {f"{i:02x}": {} for i in range(256)}
        for jid, journal in entities.items():
            shards[jid[2:4]][jid] = {"journal": journal, "aliases": aliases[jid], "observations": []}
        for row in con.execute("""SELECT o.journal_id,s.system,s.edition,s.metric_year,
              o.source_id,s.filename source_file,o.source_sheet,o.source_row,o.title,
              o.match_method,o.metrics,o.raw,o.quality_flags
              FROM observations o JOIN sources s USING(source_id)
              ORDER BY s.system,s.metric_year DESC,o.source_row"""):
            obs = dict(row)
            jid = obs.pop("journal_id")
            for key in ("metrics", "raw", "quality_flags"):
                obs[key] = json.loads(obs[key])
            shards[jid[2:4]][jid]["observations"].append(obs)
        for shard, content in shards.items():
            write_gzip(details_dir / f"{shard}.json.gz", content)
        metadata.update({"columns": columns, "catalogue": "catalogue.json.gz", "detail_base": "details/", "detail_encoding": "gzip", "snapshot_version": 1})
        (assets / "manifest.json").write_text(dumps(metadata), encoding="utf-8")
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        html = html.replace("<head>", "<head>\n  <script>window.JOURNAL_STATIC=true;</script>", 1)
        # Keep one UI source for local API mode and static-hosted mode.
        if '<script src="static-client.js"></script>' not in html:
            html = html.replace("  <script>\n  (()=>", '  <script src="static-client.js"></script>\n  <script>\n  (()=>', 1)
        html = html.replace("LOCAL EDITION", "WEB EDITION")
        for filename in ("i18n.js", "static-client.js", "app.js"):
            version = hashlib.sha256((ROOT / "web" / filename).read_bytes()).hexdigest()[:12]
            html = html.replace(f'src="{filename}"', f'src="{filename}?v={version}"')
        (output / "index.html").write_text(html, encoding="utf-8")
        (output / "static-client.js").write_bytes((ROOT / "web" / "static-client.js").read_bytes())
        (output / "i18n.js").write_bytes((ROOT / "web" / "i18n.js").read_bytes())
        (output / "app.js").write_bytes((ROOT / "web" / "app.js").read_bytes())
        (output / ".nojekyll").write_text("", encoding="utf-8")
        guide = """# 期刊索引室静态数据接口

网页在 GitHub Pages 完全由浏览器运行，无独立搜索服务器。
所有数据保持源文件的版次含义，不代表已独立核验的最新官方数据。

- `assets/manifest.json`：字段顺序、来源、数据版本、统计。
- `assets/catalogue.json.gz`：gzip JSON 二维数组，按 manifest.columns 映射为对象。
- `assets/details/{前两位ID}.json.gz`：完整详情分片。ID 为 j_abc... 时分片为 ab。
- 浏览器界面提供组合查询与 CSV 下载。静态站不提供 /api/journals HTTP 服务。

Python 读取当前站点数据（BASE 替换为该页面所在目录的 HTTPS 地址）：

```python
import gzip, json
from urllib.request import urlopen
BASE = 'https://xiaotian-liu-mkt.github.io/journal-rankings-database/'
manifest = json.load(urlopen(BASE + 'assets/manifest.json'))
payload = gzip.decompress(urlopen(BASE + 'assets/' + manifest['catalogue']).read())
records = [dict(zip(manifest['columns'], row)) for row in json.loads(payload)]
print([r for r in records if r['abdc']=='A*' and r['utd24']])
jid = next(r['journal_id'] for r in records if r['title']=='JOURNAL OF CONSUMER RESEARCH')
detail_url = BASE + 'assets/details/' + jid[2:4] + '.json.gz'
detail = json.loads(gzip.decompress(urlopen(detail_url).read()))[jid]
print(detail['observations'])
```

保留空值、0、False 的差别。JCR 学科分区见同一 categories 对象，不能将最佳分区归给所有学科。
"""
        (output / "AI_QUERY.md").write_text(guide, encoding="utf-8")
        total = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        print(dumps({"site": str(output), "entities": len(rows), "detail_shards": len(shards), "bytes": total, "initial_catalogue_bytes": (assets / "catalogue.json.gz").stat().st_size}))
    finally:
        con.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="导出 GitHub Pages 静态查询站点")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--output", default=str(ROOT / "site"))
    args = parser.parse_args()
    export_site(args.db, args.output)
