"""Load and validate curated Special Issues (Call for Papers) data."""
import datetime
import json
import re
import sys
from pathlib import Path

from . import DEFAULT_DB, ROOT
from .query import connect

DEFAULT_SPECIAL_ISSUES = ROOT / "journaldb" / "special_issues.json"

VALID_DOMAINS = frozenset({"marketing", "is", "tourism"})
VALID_STATUSES = frozenset({"ok_open", "ok_none", "blocked_manual"})
VALID_DEADLINE_TYPES = frozenset({"fixed", "extended", "abstract_first", "rolling", "unknown"})

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_JOURNAL_REQUIRED = (
    "journal_id",
    "title",
    "domain",
    "abdc_for",
    "publisher",
    "cfp_url",
    "status",
    "open_count",
    "checked_at",
    "note",
)

_ISSUE_REQUIRED = (
    "id",
    "journal_id",
    "journal_title",
    "domain",
    "title",
    "summary_zh",
    "deadline_date",
    "deadline_raw",
    "deadline_type",
    "guest_editors",
    "cfp_url",
    "checked_at",
)


def _is_iso_date(value):
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_http_url(value):
    return isinstance(value, str) and value.startswith(("http://", "https://")) and len(value) > 10


def load_special_issues(path=DEFAULT_SPECIAL_ISSUES):
    """Read special_issues.json and return the parsed dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_special_issues(data, db_path=DEFAULT_DB):
    """Validate special issues payload against schema and SQLite catalogue.

    Returns a list of error strings (empty list means valid).
    """
    errors = []
    if not isinstance(data, dict):
        return ["Top-level payload must be a JSON object."]

    if data.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, got {data.get('schema_version')!r}.")
    if not _is_iso_date(data.get("updated_at")):
        errors.append(f"updated_at must be ISO YYYY-MM-DD, got {data.get('updated_at')!r}.")
    if not isinstance(data.get("scope"), str) or not data["scope"].strip():
        errors.append("scope must be a non-empty string.")

    journals = data.get("journals")
    issues = data.get("issues")
    if not isinstance(journals, list) or not journals:
        errors.append("journals must be a non-empty list.")
        return errors
    if not isinstance(issues, list):
        errors.append("issues must be a list.")
        return errors

    catalogue_ids = None
    if db_path is not None:
        con = connect(db_path)
        try:
            catalogue_ids = {row[0] for row in con.execute("SELECT journal_id FROM catalogue")}
        finally:
            con.close()

    journals_by_id = {}
    for idx, journal in enumerate(journals):
        prefix = f"journals[{idx}]"
        if not isinstance(journal, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        missing = [field for field in _JOURNAL_REQUIRED if field not in journal]
        if missing:
            errors.append(f"{prefix} missing required fields: {', '.join(missing)}.")
            continue
        jid = journal["journal_id"]
        if not isinstance(jid, str) or not jid.strip():
            errors.append(f"{prefix}.journal_id must be a non-empty string.")
            continue
        if jid in journals_by_id:
            errors.append(f"{prefix}.journal_id duplicate: {jid}.")
        journals_by_id[jid] = journal
        if catalogue_ids is not None and jid not in catalogue_ids:
            errors.append(f"{prefix}.journal_id not found in SQLite catalogue: {jid}.")
        if not isinstance(journal["title"], str) or not journal["title"].strip():
            errors.append(f"{prefix}.title must be a non-empty string.")
        if journal["domain"] not in VALID_DOMAINS:
            errors.append(f"{prefix}.domain invalid: {journal['domain']!r}.")
        if not isinstance(journal["abdc_for"], str) or not journal["abdc_for"].strip():
            errors.append(f"{prefix}.abdc_for must be a non-empty string.")
        if not isinstance(journal["publisher"], str) or not journal["publisher"].strip():
            errors.append(f"{prefix}.publisher must be a non-empty string.")
        if not _is_http_url(journal["cfp_url"]):
            errors.append(f"{prefix}.cfp_url must be an http(s) URL: {journal['cfp_url']!r}.")
        if journal["status"] not in VALID_STATUSES:
            errors.append(f"{prefix}.status invalid: {journal['status']!r}.")
        open_count = journal["open_count"]
        if isinstance(open_count, bool) or not isinstance(open_count, int) or open_count < 0:
            errors.append(f"{prefix}.open_count must be a non-negative integer: {open_count!r}.")
        if not _is_iso_date(journal["checked_at"]):
            errors.append(f"{prefix}.checked_at must be ISO YYYY-MM-DD: {journal['checked_at']!r}.")
        if not isinstance(journal["note"], str):
            errors.append(f"{prefix}.note must be a string.")

    issue_ids = set()
    counts_by_journal = {jid: 0 for jid in journals_by_id}
    for idx, issue in enumerate(issues):
        prefix = f"issues[{idx}]"
        if not isinstance(issue, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        missing = [field for field in _ISSUE_REQUIRED if field not in issue]
        if missing:
            errors.append(f"{prefix} missing required fields: {', '.join(missing)}.")
            continue
        iid = issue["id"]
        if not isinstance(iid, str) or not iid.strip():
            errors.append(f"{prefix}.id must be a non-empty string.")
        elif iid in issue_ids:
            errors.append(f"{prefix}.id duplicate: {iid}.")
        else:
            issue_ids.add(iid)

        jid = issue["journal_id"]
        if jid not in journals_by_id:
            errors.append(f"{prefix}.journal_id not in journals list: {jid!r}.")
        else:
            counts_by_journal[jid] += 1
            expected_domain = journals_by_id[jid]["domain"]
            if issue["domain"] != expected_domain:
                errors.append(
                    f"{prefix}.domain ({issue['domain']!r}) does not match journal domain ({expected_domain!r})."
                )

        if issue["domain"] not in VALID_DOMAINS:
            errors.append(f"{prefix}.domain invalid: {issue['domain']!r}.")
        if not isinstance(issue["journal_title"], str) or not issue["journal_title"].strip():
            errors.append(f"{prefix}.journal_title must be a non-empty string.")
        if not isinstance(issue["title"], str) or not issue["title"].strip():
            errors.append(f"{prefix}.title must be a non-empty string.")
        if not isinstance(issue["summary_zh"], str) or not issue["summary_zh"].strip():
            errors.append(f"{prefix}.summary_zh must be a non-empty string.")
        if issue["deadline_date"] is not None and not _is_iso_date(issue["deadline_date"]):
            errors.append(f"{prefix}.deadline_date must be null or ISO YYYY-MM-DD: {issue['deadline_date']!r}.")
        if not isinstance(issue["deadline_raw"], str):
            errors.append(f"{prefix}.deadline_raw must be a string.")
        if issue["deadline_type"] not in VALID_DEADLINE_TYPES:
            errors.append(f"{prefix}.deadline_type invalid: {issue['deadline_type']!r}.")
        editors = issue["guest_editors"]
        if not isinstance(editors, list) or not all(isinstance(e, str) for e in editors):
            errors.append(f"{prefix}.guest_editors must be a list of strings.")
        if not _is_http_url(issue["cfp_url"]):
            errors.append(f"{prefix}.cfp_url must be an http(s) URL: {issue['cfp_url']!r}.")
        if not _is_iso_date(issue["checked_at"]):
            errors.append(f"{prefix}.checked_at must be ISO YYYY-MM-DD: {issue['checked_at']!r}.")

    for jid, journal in journals_by_id.items():
        actual = counts_by_journal[jid]
        declared = journal["open_count"]
        if not isinstance(declared, bool) and isinstance(declared, int):
            if actual != declared:
                errors.append(
                    f"Journal {jid} ({journal['title']}) open_count={declared} does not match actual issues count={actual}."
                )
            if (journal["status"] == "ok_open") != (declared > 0):
                errors.append(
                    f"Journal {jid} ({journal['title']}) status={journal['status']!r} is inconsistent with open_count={declared}."
                )

    return errors


if __name__ == "__main__":
    data = load_special_issues()
    errs = validate_special_issues(data)
    if errs:
        for err in errs:
            print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {len(data['journals'])} journals, {len(data['issues'])} issues validated.")
