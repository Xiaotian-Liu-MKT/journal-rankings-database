"""Import supplied local files, retain source rows, resolve conservative identities."""
import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT, DEFAULT_DB


def text(value):
    return "" if value is None else str(value).strip()


def norm(value):
    value = unicodedata.normalize("NFKD", text(value)).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("&", " and ")
    value = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE)
    return re.sub(r"^the\s+", "", " ".join(value.split()))


def issn(value):
    value = "".join(c for c in text(value) if unicodedata.category(c) != "Cf")
    value = re.sub(r"[\s-]", "", value).upper()
    if not re.fullmatch(r"\d{7}[\dX]", value):
        return None
    if sum(int(c) * w for c, w in zip(value[:7], range(8, 1, -1))) % 11 == (11 - (10 if value[-1] == "X" else int(value[-1]))) % 11:
        return value[:4] + "-" + value[4:]
    return None


def number(value, integer=False, decimal_comma=False):
    value = text(value)
    if decimal_comma:
        value = value.replace(",", ".")
    try:
        return int(float(value)) if integer else float(value)
    except (ValueError, TypeError):
        return None


def boolean(value):
    v = text(value).casefold()
    return True if v in ("yes", "是", "true", "1") else False if v in ("no", "否", "false", "0") else None


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def csv_rows(path, delimiter=","):
    # Preserve duplicate column names (SCImago contains Publisher twice).
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        columns = next(reader)
        seen = defaultdict(int)
        headers = []
        for col in columns:
            seen[col] += 1
            headers.append(col if seen[col] == 1 else f"{col}__{seen[col]}")
        for line, values in enumerate(reader, 2):
            if not any(text(v) for v in values):
                continue
            if len(values) != len(headers):
                raise ValueError(f"{path.name}:{line}: expected {len(headers)} columns, got {len(values)}")
            yield line, dict(zip(headers, values))


def parse_csv(path, system):
    for row, raw in csv_rows(path, ";" if system == "SJR" else ","):
        if system == "JCR":
            categories = [{"category": raw[f"Category_{n}"], "quartile": raw[f"IF Quartile(2025)_{n}"], "rank": raw[f"IF Rank(2025)_{n}"]}
                          for n in range(1, 7) if text(raw.get(f"Category_{n}"))]
            metrics = {"impact_factor": number(raw["IF(2025)"]), "categories": categories, "web_of_science": raw["Web of Science"]}
            title, ids = raw["Journal"], [raw["ISSN"], raw["EISSN"]]
        elif system == "SJR":
            metrics = {"sjr": number(raw["SJR"], decimal_comma=True), "sjr_quartile": raw["SJR Best Quartile"],
                       "publisher": raw["Publisher"], "country": raw["Country"], "source_type": raw["Type"],
                       "categories": raw["Categories"].split("; "), "areas": raw["Areas"].split("; "),
                       "open_access": boolean(raw["Open Access"]), "h_index": number(raw["H index"], True),
                       "sourceid": raw["Sourceid"]}
            title, ids = raw["Title"], re.split(r"[,;]", raw["Issn"])
        elif system == "AJG":
            metrics = {"rating": text(raw["AJG 2024"]), "field": raw["Field"], "publisher": raw["Publisher"]}
            title, ids = raw["Journal Title"], [raw["Print ISSN"], raw["E-ISSN"]]
        else:
            metrics = {"member": True, **raw}
            title, ids = raw["Journal title"], []
        yield {"row": row, "sheet": None, "title": text(title), "ids_raw": ids, "metrics": metrics, "raw": raw}


def parse_xlsx(path, system):
    import openpyxl
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in workbook:
            headers = None
            for rowno, cells in enumerate(sheet.values, 1):
                values = [text(c) for c in cells]
                if not headers:
                    if system == "CAS" or "Journal Title" in values or "Journal Name" in values:
                        # Empty/unnamed columns are still retained by position.
                        headers = [v or f"__column_{i + 1}" for i, v in enumerate(values)]
                    continue
                raw = dict(zip(headers, cells))
                if system == "CAS":
                    title, ids = values[0], []
                    metrics = {"zone": number(values[1], True), "top": boolean(values[2]), "open_access": boolean(values[3])}
                else:
                    title = text(raw.get("Journal Title", raw.get("Journal Name")))
                    ids = [raw.get("ISSN"), raw.get("ISSNOnline", raw.get("ISSN Online"))]
                    rank_keys = [k for k in headers if "rating" in k.casefold() or "ABDC List" in k or k == "ABDC Ranking"]
                    metrics = {"rating": text(raw.get(rank_keys[0])).upper() if rank_keys else None,
                               "publisher": text(raw.get("Publisher")),
                               "field": text(raw.get("FoR", raw.get("Field of Research", raw.get("ABDC FoR code")))),
                               "start_year": text(raw.get("Year Inception", raw.get("Start year")))}
                    if metrics["rating"] not in ("A*", "A", "B", "C", ""):
                        if title:
                            raise ValueError(f"Unexpected ABDC row {sheet.title}:{rowno}: {title} / {metrics['rating']}")
                        continue
                    if metrics["rating"] == "":
                        metrics["rating"] = None
                if title:
                    yield {"row": rowno, "sheet": sheet.title, "title": title, "ids_raw": ids, "metrics": metrics, "raw": raw}
    finally:
        workbook.close()


# Explicit aliases bridge differently labelled titles within the supplied lists.
# They are never used for fuzzy matching, and only apply to a unique local target.
TITLE_ALIASES = {
    norm("Journal on Computing"): norm("INFORMS Journal on Computing"),
    norm("M&SOM-MANUFACTURING & SERVICE OPERATIONS MANAGEMENT"): norm("Manufacturing & Service Operations Management"),
}


def build(root=ROOT, destination=DEFAULT_DB):
    root, destination = Path(root), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".building.sqlite")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    try:
        con.executescript((Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8"))
        con.execute("INSERT INTO metadata VALUES (?,?)", ("built_at", datetime.now(timezone.utc).isoformat()))
        con.execute("INSERT INTO metadata VALUES (?,?)", ("schema_version", "1"))
        paths = {p.name: p for p in root.iterdir() if p.is_file()}
        jobs = []
        for p in paths.values():
            if p.name.startswith("2025 Journal Impact") or p.name.startswith("JCR "):
                jobs.append((0, p, "JCR", "2025 (source-labelled; unverified)", 2025))
            elif p.name.startswith("scimagojr") and p.suffix == ".csv":
                jobs.append((1, p, "SJR", "2025", 2025))
            elif p.name.startswith("ABS ") and p.suffix == ".txt":
                jobs.append((2, p, "AJG", "2024", 2024))
            elif p.name.startswith("ABDC") and p.suffix == ".xlsx":
                jobs.append((3, p, "ABDC", "multiple", None))
            elif p.name.startswith("中科院") and p.suffix == ".xlsx":
                jobs.append((4, p, "CAS", "2025", 2025))
            elif p.name in ("FT50.txt", "UTD24.txt"):
                system = p.stem
                jobs.append((5, p, system, "2026", 2026))
        if len(jobs) != 8:
            raise ValueError(f"Expected the 8 supplied source files; found {len(jobs)}")
        groups, by_id, by_title = {}, defaultdict(set), defaultdict(set)
        hashes = {}
        for _, path, system, edition, year in sorted(jobs, key=lambda x: (x[0], x[1].name)):
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            source_id = system.lower() + "_" + sha[:12]
            if sha in hashes:
                dupe_id = source_id + "_alias"
                con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)", (dupe_id, path.name, sha, system, edition, year, 0, hashes[sha], "Identical file bytes; not imported twice"))
                continue
            hashes[sha] = source_id
            if system == "ABDC":
                rows = list(parse_xlsx(path, system))
                # Latest worksheet supplies canonical names; every historical row stays queryable.
                rows.sort(key=lambda r: (-int(r["sheet"][:4]), r["row"]))
            else:
                rows = parse_xlsx(path, system) if path.suffix == ".xlsx" else parse_csv(path, system)
            source_ids = {}
            for row in rows:
                row_edition = row["sheet"][:4] if system == "ABDC" else edition
                sid = source_id + "_" + row_edition if system == "ABDC" else source_id
                if sid not in source_ids:
                    source_ids[sid] = 0
                    note = "Year is the supplied header label, not independently verified" if system == "JCR" else ""
                    if system == "CAS":
                        note = "Source gives one zone but no category or major/minor classification; retain as supplied"
                    con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)", (sid, path.name, sha, system, row_edition, int(row_edition[:4]), 0, None, note))
                source_ids[sid] += 1
                key = norm(row["title"])
                ids = {issn(v) for v in row["ids_raw"]} - {None}
                flags = ["invalid_issn:" + text(v) for v in row["ids_raw"] if text(v) and text(v).upper() not in ("N/A", "NA", "-") and not issn(v)]
                candidates = set().union(*(by_id[v] for v in ids)) if ids else set()
                title_candidates = by_title[key]
                method, target = "new", None
                if len(candidates) == 1:
                    target, method = next(iter(candidates)), "issn"
                elif len(candidates) > 1:
                    common = candidates & title_candidates
                    if candidates <= title_candidates:
                        # A row can bridge print/electronic identifiers from two sources.
                        # Only consolidate when every candidate already has exactly this
                        # normalized title; never merge differently titled candidates here.
                        target = next(j for j in groups if j in candidates)
                        method = "issn_bridge_same_title"
                        for old in sorted(candidates - {target}):
                            previous = groups.pop(old)
                            group = groups[target]
                            for k in ("ids", "aliases", "flags"):
                                group[k].update(previous[k])
                            group["observations"].extend(previous["observations"])
                            con.execute("UPDATE observations SET journal_id=? WHERE journal_id=?", (target, old))
                            con.execute("DELETE FROM journals WHERE journal_id=?", (old,))
                            for value in previous["ids"]:
                                by_id[value].discard(old)
                                by_id[value].add(target)
                            for value in previous["aliases"]:
                                by_title[norm(value)].discard(old)
                                by_title[norm(value)].add(target)
                    elif len(common) == 1:
                        target, method = next(iter(common)), "issn_and_title_disambiguation"
                    else:
                        exact_ids = {j for j in candidates if ids <= groups[j]["ids"]}
                        if len(exact_ids) == 1:
                            target, method = next(iter(exact_ids)), "issn_set_disambiguation"
                    if method != "issn_bridge_same_title":
                        flags.append("multiple_issn_candidates")
                elif len(title_candidates) == 1:
                    candidate = next(iter(title_candidates))
                    if not ids or not groups[candidate]["ids"]:
                        target, method = candidate, "normalized_title"
                    else:
                        flags.append("same_title_disjoint_issn")
                elif len(title_candidates) > 1:
                    flags.append("ambiguous_title")
                if target is None and not ids and key in TITLE_ALIASES:
                    aliases = by_title[TITLE_ALIASES[key]]
                    if len(aliases) == 1:
                        target, method = next(iter(aliases)), "explicit_title_alias"
                if target is None:
                    seed = f"{sid}|{row['sheet']}|{row['row']}|{key}"
                    target = "j_" + hashlib.sha256(seed.encode()).hexdigest()[:16]
                    groups[target] = {"ids": set(), "title": row["title"], "observations": [], "aliases": set(), "flags": set()}
                    con.execute("INSERT INTO journals VALUES (?,?,?)", (target, row["title"], key))
                group = groups[target]
                group["ids"].update(ids)
                group["aliases"].add(row["title"])
                group["flags"].update(flags)
                by_title[key].add(target)
                for value in ids:
                    by_id[value].add(target)
                con.execute("INSERT INTO observations(journal_id,source_id,source_sheet,source_row,title,match_method,metrics,raw,quality_flags) VALUES (?,?,?,?,?,?,?,?,?)",
                            (target, sid, row["sheet"], row["row"], row["title"], method, dumps(row["metrics"]), dumps(row["raw"]), dumps(flags)))
                group["observations"].append((system, int(row_edition[:4]), row["metrics"]))
            for sid, count in source_ids.items():
                con.execute("UPDATE sources SET row_count=? WHERE source_id=?", (count, sid))
        for jid, group in groups.items():
            con.executemany("INSERT INTO identifiers VALUES (?,?)", [(jid, v) for v in sorted(group["ids"])])
            con.executemany("INSERT INTO aliases VALUES (?,?,?)", [(jid, v, norm(v)) for v in sorted(group["aliases"])])
            summary = summarize(jid, group)
            columns = list(summary)
            con.execute(f"INSERT INTO catalogue({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", list(summary.values()))
        con.execute("CREATE VIRTUAL TABLE journal_search USING fts5(journal_id UNINDEXED,search_text,tokenize='unicode61 remove_diacritics 2')")
        con.execute("INSERT INTO journal_search SELECT journal_id, search_text FROM catalogue")
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()
        count = con.execute("SELECT count(*) FROM journals").fetchone()[0]
        records = con.execute("SELECT count(*) FROM observations").fetchone()[0]
        con.close()
        tmp.replace(destination)
        export(destination)
        print(dumps({"database": str(destination), "journals": count, "records": records}))
    except BaseException:
        con.close()
        if tmp.exists():
            tmp.unlink()
        raise


def summarize(jid, group):
    by_system = defaultdict(list)
    for system, year, metrics in group["observations"]:
        by_system[system].append((year, metrics))
    # Current means the latest supplied edition of that system, never a historical fallback.
    years = {"ABDC": 2025, "AJG": 2024, "CAS": 2025, "JCR": 2025, "SJR": 2025, "FT50": 2026, "UTD24": 2026}
    current = {s: [m for y, m in values if y == years[s]] for s, values in by_system.items()}
    def unique(system, field):
        values = [m.get(field) for m in current.get(system, []) if m.get(field) is not None and m.get(field) != ""]
        distinct = {dumps(v) for v in values}
        if len(distinct) > 1:
            group["flags"].add(f"conflicting_current_value:{system}:{field}")
            return None
        return values[0] if values else None
    subjects = set()
    for s, values in current.items():
        for m in values:
            if s == "JCR":
                subjects.update(c["category"] for c in m["categories"])
            elif s == "SJR":
                subjects.update(re.sub(r"\s*\(Q[1-4]\)$", "", v) for v in m["categories"])
                subjects.update(m["areas"])
            elif s == "AJG" and m.get("field"):
                subjects.add(m["field"])
    quartiles = {c["quartile"] for m in current.get("JCR", []) for c in m["categories"] if c["quartile"] in ("Q1", "Q2", "Q3", "Q4")}
    result = {"journal_id": jid, "title": group["title"], "issns": dumps(sorted(group["ids"])),
              "abdc": unique("ABDC", "rating"), "abdc_year": 2025 if current.get("ABDC") else None,
              "ajg": unique("AJG", "rating"), "ajg_year": 2024 if current.get("AJG") else None,
              "cas_zone": unique("CAS", "zone"), "cas_top": unique("CAS", "top"), "cas_year": 2025 if current.get("CAS") else None,
              "impact_factor": unique("JCR", "impact_factor"), "jcr_quartile": min(quartiles) if quartiles else None,
              "jcr_year": 2025 if current.get("JCR") else None, "sjr": unique("SJR", "sjr"),
              "sjr_quartile": unique("SJR", "sjr_quartile"), "sjr_year": 2025 if current.get("SJR") else None,
              "ft50": bool(current.get("FT50")), "utd24": bool(current.get("UTD24")),
              "publisher": unique("AJG", "publisher") or unique("ABDC", "publisher") or unique("SJR", "publisher"),
              "country": unique("SJR", "country"), "source_type": unique("SJR", "source_type"), "subjects": dumps(sorted(subjects))}
    result["search_text"] = " ".join(sorted(group["aliases"]) + sorted(group["ids"]) + [v.replace("-", "") for v in sorted(group["ids"])] + sorted(subjects))
    result["quality_flags"] = dumps(sorted(group["flags"]))
    return result


def export(database):
    from .query import connect, decode
    con = connect(database)
    rows = con.execute("SELECT * FROM catalogue ORDER BY title COLLATE NOCASE,journal_id")
    output = database.parent
    with (output / "journals.csv").open("w", encoding="utf-8-sig", newline="") as cf, (output / "journals.jsonl").open("w", encoding="utf-8") as jf:
        writer = None
        for row in rows:
            obj = decode(row)
            obj.pop("search_text", None)
            jf.write(dumps(obj) + "\n")
            flat = {k: "; ".join(map(str, v)) if isinstance(v, list) else v for k, v in obj.items()}
            if writer is None:
                writer = csv.DictWriter(cf, fieldnames=list(flat))
                writer.writeheader()
            writer.writerow(flat)
    con.close()
