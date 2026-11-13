"""Training-free construction-graph retrieval for a CAD case library.

This module is the "one change" from the report: it replaces flat document
similarity over case-library entries with retrieval over serialized
construction graphs, plus feature-level subgraph entries obtained by backward
traversal from a result node.

The graph schema is deliberately plain JSON so the module runs without any
CAD SDK:

    graph = {
        "nodes": [
            {"id": "n1", "op": "make_box_rsolid", "role": "base",
             "params": {"L": 40.0, "W": 20.0, "H": 8.0}, "tags": ["base"]},
            ...
        ],
        "edges": [["n1", "n2"], ...],      # [consumer, consumed] or [src, dst]
        "results": ["n5"],                 # designated result nodes
    }

Edge direction convention: an edge [a, b] means "a consumes b" (b is an input
to a). Results have no consumers.

Scoring mirrors the hybrid of the original system (0.6 vector / 0.4 lexical):
    score = W_VEC * cos(query_vec, entry_vec) + W_LEX * lexical_overlap(query, entry_text)
`query_vec`/`entry_vec` are optional; with vectors absent the score degrades
to pure lexical overlap, so the module is runnable with no embedding model.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Sequence, Tuple

W_VEC = 0.6
W_LEX = 0.4

_NODE_RE = re.compile(r"[A-Za-z0-9_]+")


# ---------------------------------------------------------------------------
# serialization
# ---------------------------------------------------------------------------

def _fmt_params(params: Optional[Dict]) -> str:
    if not params:
        return ""
    return " ".join(f"{k}={_fmt_value(v)}" for k, v in sorted(params.items()))


def _fmt_value(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (int, float, str, bool)):
        return str(v)
    return str(v)


def _topological_order(graph: Dict) -> List[str]:
    """Node ids in dependency order (inputs before consumers)."""
    nodes = [n["id"] for n in graph["nodes"]]
    consumers_of = defaultdict(list)   # b -> [a, ...] for edge [a, b]
    indegree = {n: 0 for n in nodes}
    for a, b in graph.get("edges", []):
        consumers_of[b].append(a)
        indegree[a] += 1
    queue = deque(sorted(n for n in nodes if indegree[n] == 0))
    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in sorted(consumers_of[n]):
            indegree[m] -= 1
            if indegree[m] == 0:
                queue.append(m)
    if len(order) != len(nodes):
        raise ValueError("graph has a cycle; construction graphs must be acyclic")
    return order


def serialize_graph(graph: Dict) -> str:
    """Serialize a whole construction graph to retrieval text.

    Dependencies are written out ('<- n1') so a text embedding of this string
    carries the structure, not just the operation vocabulary.
    """
    by_id = {n["id"]: n for n in graph["nodes"]}
    inputs_of = defaultdict(list)      # a -> [b, ...] for edge [a, b]
    for a, b in graph.get("edges", []):
        inputs_of[a].append(b)
    lines = []
    for nid in _topological_order(graph):
        n = by_id[nid]
        deps = ",".join(sorted(inputs_of.get(nid, [])))
        tags = ",".join(n.get("tags", []))
        line = f"{n['op']}({n.get('role', '')})"
        params = _fmt_params(n.get("params"))
        if params:
            line += f" {params}"
        if tags:
            line += f" tags={tags}"
        if deps:
            line += f" <- {deps}"
        lines.append(line)
    return "\n".join(lines)


def backward_subgraph(graph: Dict, seed: str, max_nodes: int = 8) -> Dict:
    """The feature subgraph that produced `seed`: seed plus everything its
    value depends on (backward traversal over consumption edges), bounded so
    subgraph entries stay feature-sized."""
    inputs_of = defaultdict(list)      # a -> [b, ...]
    for a, b in graph.get("edges", []):
        inputs_of[a].append(b)
    seen, queue = {seed}, deque([seed])
    while queue and len(seen) < max_nodes:
        cur = queue.popleft()
        for nxt in inputs_of.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    node_set = set(by["id"] for by in graph["nodes"]) & seen
    nodes = [n for n in graph["nodes"] if n["id"] in node_set]
    edges = [[a, b] for a, b in graph.get("edges", []) if a in node_set and b in node_set]
    return {"nodes": nodes, "edges": edges, "results": [seed]}


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def _tokens(text: str) -> List[str]:
    return _NODE_RE.findall(text.lower())


def lexical_overlap(query: str, entry_text: str) -> float:
    """Fraction of query tokens present in the entry text (training-free
    fallback). Query coverage, not token F1: a full serialization is longer
    than the query by design, so precision against the entry would punish
    exactly the structural detail we added."""
    q, e = _tokens(query), set(_tokens(entry_text))
    if not q:
        return 0.0
    hit = sum(1 for t in q if t in e)
    return hit / len(q)


def _cos(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def score_entry(query_text: str,
                query_vec: Optional[Sequence[float]],
                entry_text: str,
                entry_vec: Optional[Sequence[float]]) -> float:
    s = 0.0
    if query_vec is not None and entry_vec is not None:
        s += W_VEC * _cos(query_vec, entry_vec)
    s += W_LEX * lexical_overlap(query_text, entry_text)
    return s


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------

def build_library_entry(case_id: str,
                        graph: Dict,
                        document_text: str,
                        doc_vec: Optional[Sequence[float]] = None,
                        subgraph_max_nodes: int = 8) -> List[Dict]:
    """One case -> its library entries: the whole graph plus one subgraph
    entry per result node (feature-level reuse without extra training)."""
    entries = [{
        "case_id": case_id,
        "kind": "full_graph",
        "text": serialize_graph(graph),
        "vec": doc_vec,
    }]
    for seed in graph.get("results", []):
        sub = backward_subgraph(graph, seed, max_nodes=subgraph_max_nodes)
        entries.append({
            "case_id": case_id,
            "kind": f"subgraph:{seed}",
            "text": serialize_graph(sub),
            "vec": doc_vec,   # training-free: reuse the case vector for its subgraphs
        })
    # document text stays available so the library can mix both signals
    entries.append({
        "case_id": case_id,
        "kind": "document",
        "text": document_text,
        "vec": doc_vec,
    })
    return entries


def retrieve(query_text: str,
             query_vec: Optional[Sequence[float]],
             library: List[Dict],
             k: int = 3,
             kinds: Optional[Sequence[str]] = None) -> List[Tuple[float, str, str]]:
    """Top-k library entries. `kinds` filters entry kinds (e.g. only
    'full_graph' entries to disable feature-level reuse). Returns
    (score, case_id, kind) sorted best-first."""
    pool = [e for e in library if kinds is None or e["kind"] in kinds]
    scored = [(score_entry(query_text, query_vec, e["text"], e.get("vec")),
               e["case_id"], e["kind"]) for e in pool]
    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    return scored[:k]
