"""Derived title initials for discovery only; never journal identity aliases."""
import re
from functools import lru_cache

from .build import norm


CONNECTORS = frozenset("a an the of and for in on at to by with from".split())


def acronym_key(value):
    """Accept compact or dotted/spaced initials, case-insensitively."""
    value = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z.\s-]*", value):
        return ""
    key = re.sub(r"[.\s-]", "", value)
    return key if 2 <= len(key) <= 12 else ""


def search_text(value):
    value = str(value or "").strip()
    # E.J.M. and E J M should search as EJM, not as three broad word prefixes.
    if re.fullmatch(r"(?:[a-z][.\s-]+)+[a-z]\.?", value, flags=re.IGNORECASE):
        return acronym_key(value) or value
    return value


@lru_cache(maxsize=100_000)
def title_acronyms(title):
    words = norm(title).split()
    # norm() drops a leading article for identity matching; keep that variant
    # here so source titles such as The Accounting Review also yield TAR.
    if re.match(r"^\s*the\s+", str(title or ""), flags=re.IGNORECASE):
        words.insert(0, "the")
    if len(words) < 2:
        return ()
    # Retain both JOM and JM for Journal of Marketing, for example.
    candidates = {"".join(word[0] for word in words),
                  "".join(word[0] for word in words if word not in CONNECTORS)}
    return tuple(sorted(key for key in candidates if re.fullmatch(r"[a-z]{2,12}", key)))


def matches_acronym(title, key):
    return key in title_acronyms(title)
