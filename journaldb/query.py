"""Read-only query layer shared by the CLI and HTTP interface."""
import json
import re
import sqlite3
from pathlib import Path

from . import DEFAULT_DB
from .build import norm


NOTES = [
    "所有版本与指标来自所提供的本地文件，未联网核验。JCR 年份按源文件 IF(2025) 表头保留。",
    "JCR 概览与筛选使用最佳分区；每个学科的分区和名次见详情。SJR 分区为源文件 SJR Best Quartile。",
    "中科院源文件仅有一个分区、Top、OA，未提供大类/小类或学科，不能据此推断。",
    "ABDC 概览仅取 2025 版，2010/2013/2016/2019/2022 历史版在详情中保留；未在 2025 版出现时不以旧评级填充。",
    "空值表示本地文件未提供或当前值冲突。FT50/UTD24 的 false 仅表示未匹配到本地名单，不代表官方未收录。",
    "SCImago 原始数据包含 journal、book series、conference and proceedings、trade journal，均保留 source_type。",
    "ISSN 优先并校验校验位；刊名只做严格标准化匹配，两个已知且不相交的 ISSN 集合不因同名自动合并。",
    "SCIE、SSCI、AHCI、ESCI 为无年份的本地 Web of Science 名录，独立于 JCR 指标版次；空数组仅表示未匹配本地名单。",
]


def connect(path=DEFAULT_DB):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"数据库不存在：{path}。请先运行 python -m journaldb build")
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def decode(row):
    result = dict(row)
    for key in ("issns", "wos_indexes", "languages", "subjects", "quality_flags"):
        if key in result:
            result[key] = json.loads(result[key])
    for key in ("ft50", "utd24", "cas_top"):
        if result.get(key) is not None:
            result[key] = bool(result[key])
    return result


def like(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def filters(params):
    clauses, values = [], []
    q = str(params.get("q", "")).strip()
    if len(q) > 500:
        raise ValueError("查询词最多 500 字符")
    if q:
        compact = re.sub(r"[\s-]", "", q).upper()
        if re.fullmatch(r"\d{7}[\dX]", compact):
            clauses.append("c.journal_id IN (SELECT journal_id FROM identifiers WHERE issn=?)")
            values.append(compact[:4] + "-" + compact[4:])
        else:
            # Literal substring plus normalized alias matching, never execute user FTS syntax.
            tokens = re.findall(r"\w+", norm(q), flags=re.UNICODE)
            fts = " AND ".join('"' + token.replace('"', '""') + '"*' for token in tokens)
            normalized = norm(q)
            clauses.append("(c.search_text LIKE ? ESCAPE '\\'" +
                           (" OR c.journal_id IN (SELECT journal_id FROM aliases WHERE normalized_title LIKE ? ESCAPE '\\')" if normalized else "") +
                           (" OR c.journal_id IN (SELECT journal_id FROM journal_search WHERE journal_search MATCH ?)" if fts else "") + ")")
            values.append(like(q))
            if normalized:
                values.append(like(normalized))
            if fts:
                values.append(fts)
    allowed = {"abdc": ("A*", "A", "B", "C"), "ajg": ("4*", "4", "3", "2", "1"),
               "cas": ("1", "2", "3", "4"), "jcr_quartile": ("Q1", "Q2", "Q3", "Q4"),
               "sjr_quartile": ("Q1", "Q2", "Q3", "Q4"), "ft50": ("0", "1"), "utd24": ("0", "1"),
               "source_type": ("journal", "book series", "conference and proceedings", "trade journal")}
    for field, choices in allowed.items():
        value = params.get(field)
        if value is None or value == "":
            continue
        value = str(value)
        if value not in choices:
            raise ValueError(f"{field} 必须为 {', '.join(choices)}")
        clauses.append("c." + ("cas_zone" if field == "cas" else field) + "=?")
        values.append(value)
    wos_index = params.get("wos_index")
    if wos_index not in (None, ""):
        wos_index = str(wos_index)
        if wos_index not in ("SCIE", "SSCI", "AHCI", "ESCI"):
            raise ValueError("wos_index 必须为 SCIE、SSCI、AHCI 或 ESCI")
        clauses.append("EXISTS(SELECT 1 FROM json_each(c.wos_indexes) WHERE value=?)")
        values.append(wos_index)
    if params.get("subject"):
        clauses.append("EXISTS(SELECT 1 FROM json_each(c.subjects) WHERE value LIKE ? ESCAPE '\\')")
        values.append(like(str(params["subject"])))
    if params.get("min_if") not in (None, ""):
        try:
            minimum = float(params["min_if"])
        except (ValueError, TypeError):
            raise ValueError("min_if 必须为非负有限数值") from None
        import math
        if not math.isfinite(minimum) or minimum < 0:
            raise ValueError("min_if 必须为非负有限数值")
        clauses.append("c.impact_factor>=?")
        values.append(minimum)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), values


def selection(params):
    where, values = filters(params)
    sort = str(params.get("sort", "title"))
    if sort not in ("title", "impact_factor", "sjr"):
        raise ValueError("sort 必须为 title、impact_factor 或 sjr")
    order = str(params.get("order", "asc")).lower()
    if order not in ("asc", "desc"):
        raise ValueError("order 必须为 asc 或 desc")
    priority = ""
    if params.get("q") and sort == "title":
        # A full journal title should be the first result even if all query tokens
        # also occur in other journals' subject labels.
        priority = "NOT EXISTS(SELECT 1 FROM aliases a WHERE a.journal_id=c.journal_id AND a.normalized_title=?),"
        values.append(norm(params["q"]))
    order_sql = f" ORDER BY {priority}c.{sort} IS NULL,c.{sort} COLLATE NOCASE {order},c.journal_id"
    return where, values, order_sql


def search(con, **params):
    where, values, order_sql = selection(params)
    try:
        limit, offset = int(params.get("limit", 50)), int(params.get("offset", 0))
    except (ValueError, TypeError):
        raise ValueError("limit 和 offset 必须为整数") from None
    if not 1 <= limit <= 500 or offset < 0:
        raise ValueError("limit 范围为 1–500，offset 不得为负")
    _, count_values = filters(params)
    total = con.execute("SELECT count(*) FROM catalogue c" + where, count_values).fetchone()[0]
    rows = con.execute("SELECT c.* FROM catalogue c" + where + order_sql + " LIMIT ? OFFSET ?", values + [limit, offset])
    results = []
    for row in rows:
        obj = decode(row)
        obj.pop("search_text", None)
        results.append(obj)
    return {"results": results, "total": total, "limit": limit, "offset": offset}


def detail(con, journal_id):
    row = con.execute("SELECT * FROM catalogue WHERE journal_id=?", (journal_id,)).fetchone()
    if row is None:
        return None
    journal = decode(row)
    journal.pop("search_text", None)
    observations = []
    for row in con.execute("""SELECT s.system,s.edition,s.metric_year,o.source_id,s.filename source_file,
                            o.source_sheet,o.source_row,o.title,o.match_method,o.metrics,o.raw,o.quality_flags
                            FROM observations o JOIN sources s USING(source_id) WHERE journal_id=?
                            ORDER BY s.system,s.metric_year DESC,o.source_row""", (journal_id,)):
        obj = dict(row)
        for key in ("metrics", "raw", "quality_flags"):
            obj[key] = json.loads(obj[key])
        observations.append(obj)
    return {"journal": journal, "aliases": [r[0] for r in con.execute("SELECT title FROM aliases WHERE journal_id=? ORDER BY title", (journal_id,))], "observations": observations}


def meta(con):
    stats = {"journals": con.execute("SELECT count(*) FROM journals").fetchone()[0],
             "records": con.execute("SELECT count(*) FROM observations").fetchone()[0],
             "sources": con.execute("SELECT count(*) FROM sources WHERE duplicate_of IS NULL").fetchone()[0],
             "files": con.execute("SELECT count(DISTINCT filename) FROM sources").fetchone()[0],
             "ft50": con.execute("SELECT sum(ft50) FROM catalogue").fetchone()[0],
             "utd24": con.execute("SELECT sum(utd24) FROM catalogue").fetchone()[0],
             "wos_index_counts": {index: con.execute("SELECT count(*) FROM catalogue WHERE EXISTS(SELECT 1 FROM json_each(wos_indexes) WHERE value=?)", (index,)).fetchone()[0]
                                  for index in ("SCIE", "SSCI", "AHCI", "ESCI")}}
    return {"stats": stats, "sources": [dict(r) for r in con.execute("SELECT * FROM sources ORDER BY system,metric_year DESC")],
            "notes": NOTES, "built_at": con.execute("SELECT value FROM metadata WHERE key='built_at'").fetchone()[0]}
