"""Build and query the curated unified taxonomy without inferring classifications."""
import json
from functools import lru_cache
from pathlib import Path

from . import ROOT


def _key(value):
    return " ".join(str(value or "").casefold().replace("&", "and").split())


@lru_cache(maxsize=1)
def load_taxonomy():
    """Load the versioned, curator-owned crosswalk only when taxonomy is used."""
    path = ROOT / "journaldb" / "taxonomy_data.json"
    if not path.is_file():
        raise FileNotFoundError("缺少 journaldb/taxonomy_data.json；无法使用统一分类")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("mappings"), dict):
        raise ValueError("taxonomy_data.json 格式无效")
    nodes = {node["id"]: node for node in data["nodes"]}
    if len(nodes) != len(data["nodes"]):
        raise ValueError("taxonomy_data.json 含重复节点 ID")
    for node in nodes.values():
        parent = node.get("parent_id")
        if parent is not None and parent not in nodes:
            raise ValueError(f"taxonomy 节点父级不存在：{node['id']}")
    normalized_mappings = {}
    for system, mapping in data["mappings"].items():
        normalized_mappings[system] = {}
        for raw, node_ids in mapping.items():
            key = _key(raw)
            previous = normalized_mappings[system].setdefault(key, node_ids)
            if previous != node_ids:
                raise ValueError(f"taxonomy {system} 存在冲突的规范化映射：{raw}")
    data["_nodes"] = nodes
    data["_normalized_mappings"] = normalized_mappings
    return data


def taxonomy_metadata(data=None):
    data = data or load_taxonomy()
    return {key: data[key] for key in ("version", "sources", "nodes") if key in data}


# Public name used by HTTP/static adapters.  It intentionally returns no
# implementation caches such as _nodes or _normalized_mappings.
def taxonomy_definition():
    return taxonomy_metadata()


def root_for(node_id, nodes):
    node = nodes[node_id]
    while node.get("parent_id") is not None:
        node = nodes[node["parent_id"]]
    return node["id"]


def current_taxonomy_paths(current, wos_current, data=None):
    """Return canonical paths and retained source evidence for one journal.

    The caller supplies only current source metrics.  Raw labels that lack an
    explicit crosswalk are deliberately absent rather than guessed.
    """
    data = data or load_taxonomy()
    nodes, mappings = data["_nodes"], data["mappings"]
    paths = {}

    def add(node_id, evidence):
        if node_id not in nodes:
            raise ValueError(f"taxonomy mapping references unknown node: {node_id}")
        paths.setdefault(node_id, []).append(evidence)

    def mapped(system, raw, evidence):
        node_ids = mappings.get(system, {}).get(raw)
        if node_ids is None:
            node_ids = data["_normalized_mappings"].get(system, {}).get(_key(raw), [])
        for node_id in node_ids:
            add(node_id, evidence)

    # SJR areas map to the taxonomy roots only by an exact label match.
    roots_by_label = {_key(node.get("label_en")): node_id for node_id, node in nodes.items()
                      if node.get("parent_id") is None}
    for metric in current.get("SJR", []):
        for area in metric.get("areas", []):
            node_id = roots_by_label.get(_key(area))
            if node_id:
                add(node_id, {"system": "SJR", "edition": "2025", "field": "area", "value": area, "relation": "direct"})
        for category in metric.get("categories", []):
            raw = category.rsplit(" (Q", 1)[0]
            mapped("SJR", raw, {"system": "SJR", "edition": "2025", "field": "category", "value": raw, "relation": "direct"})
    for metric in current.get("AJG", []):
        raw = metric.get("field")
        if raw:
            mapped("AJG", raw, {"system": "AJG", "edition": "2024", "field": "field", "value": raw, "relation": "direct"})
    for metric in current.get("ABDC", []):
        raw = metric.get("field")
        if raw:
            mapped("ABDC", raw, {"system": "ABDC", "edition": "2025", "field": "field", "value": raw, "relation": "direct"})
    for metric in current.get("JCR", []):
        for category in metric.get("categories", []):
            raw = category.get("category")
            if raw:
                mapped("WOS", raw, {"system": "JCR", "edition": "2025 (source-labelled; unverified)", "field": "category", "value": raw, "relation": "direct"})
    for system, records in wos_current.items():
        for metric in records:
            for raw in metric.get("categories", []):
                mapped("WOS", raw, {"system": system, "edition": "undated", "field": "category", "value": raw, "relation": "direct"})

    # A curator can declare an AJG refinement of a broader canonical leaf.
    # Evidence from the broad node is retained but cannot be read as support
    # for the narrower classification because relation remains "broader".
    refinements = {}
    for finer_id, node in nodes.items():
        if finer_id not in paths:
            continue
        for broader_id in node.get("refines", []):
            if broader_id in paths and root_for(broader_id, nodes) == root_for(finer_id, nodes):
                refinements.setdefault(broader_id, []).append(finer_id)
    for broader_id, finer_ids in refinements.items():
        broader_evidence = paths.pop(broader_id)
        # A broad source assignment supports every retained finer branch only
        # at the broad level.  Do not lose it when multiple finer branches are
        # simultaneously assigned to one journal.
        for finer_id in finer_ids:
            paths[finer_id].extend({**evidence, "relation": "broader"} for evidence in broader_evidence)

    result = []
    for node_id, evidence in paths.items():
        broad_id = root_for(node_id, nodes)
        result.append({"broad_id": broad_id, "subcategory_id": None if node_id == broad_id else node_id,
                       "evidence": evidence})

    # Root-only evidence belongs with a more specific path in the same branch.
    # Its relation makes clear it only supports the broad assignment.
    for root_id in [path["broad_id"] for path in result if path["subcategory_id"] is None]:
        detailed = [path for path in result if path["broad_id"] == root_id and path["subcategory_id"]]
        root_path = next(path for path in result if path["broad_id"] == root_id and path["subcategory_id"] is None)
        if detailed:
            for path in detailed:
                path["evidence"].extend({**item, "relation": "broader"} for item in root_path["evidence"])
            result.remove(root_path)
    return sorted(result, key=lambda path: (path["broad_id"], path["subcategory_id"] or ""))
