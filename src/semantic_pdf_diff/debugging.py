"""`semantic-pdf-diff debug`: what a store's runs asked and what failed, with counts and the errors recorded, in a few
lines to read off a screen (the owner, 2026-10-29: "We should probably add a `semantic-pdf-diff debug` option that
prints error information and error counts. I'm not very able to copy a large script manually across two domains.").

Nothing of the documents is printed but what a server's error quotes: the version, the endpoint and the models the last
comparison used (the store's settings, before one; URLs redacted), the requests the store's runs asked by step
(answered, failed, never answered: not sent, as after sending stopped), the last comparison's counts and how its
subjects were matched (counts only: the sources as A and B, no names), and the errors the answers cache recorded, the
most frequent first. A failure is recorded once a request has failed its retries; a request
never sent isn't.
"""
import os
import platform
from collections import Counter
from types import SimpleNamespace

ERROR_CHARACTERS = 300  # of each error printed: a server's may quote the whole request
# the steps whose errors are told apart by the region asked: an extraction's text, table, tile, overview or figure
# (the owner's run, 2026-10-29: "extract 763 Truncated")
BY_REGION = ("extract", "triage")

def short(error):
    """An error on one line, at most ERROR_CHARACTERS."""
    text = " ".join((error or "no error recorded").split())
    return text if len(text) <= ERROR_CHARACTERS else text[:ERROR_CHARACTERS - 3] + "..."

ENDPOINT = ("base_url", "model", "rerank_model", "rerank_api", "rerank_url", "embed_model", "embed_url",
            "embed_dimensions")

def endpoint(values):
    """Where settings ask, and which models ({name: value}: a comparison's recorded settings, or the store's):
    {"base_url", "model", "reranker", "embedding"} (URLs redacted; None where none is named)."""
    from . import embed, rerank
    from .llm import redact_url
    settings = SimpleNamespace(**{name: values.get(name) for name in ENDPOINT})
    try:
        reranked_at = redact_url(rerank.endpoint(settings)) if settings.rerank_model else ""
    except ValueError as e:
        reranked_at = str(e)
    return {"base_url": redact_url(settings.base_url), "model": settings.model,
            "reranker": {"model": settings.rerank_model, "api": settings.rerank_api, "url": reranked_at}
            if settings.rerank_model else None,
            "embedding": {"model": settings.embed_model, "url": redact_url(embed.endpoint(settings)),
                          "dimensions": settings.embed_dimensions} if settings.embed_model else None}

def steps(roles, outcomes):
    """The requests by step ({hash: (role, region)}, {hash: (outcome, error)}): ([{step, asked, answered, failed,
    never_answered}], Counter of (step, error) for those failed, an extraction's step with its region: "extract
    (tile)")."""
    counts, errors = {}, Counter()
    for query, (role, region) in roles.items():
        row = counts.setdefault(role or "other", {"step": role or "other", "asked": 0, "answered": 0, "failed": 0,
                                                  "never_answered": 0})
        row["asked"] += 1
        outcome, error = outcomes.get(query, (None, None))
        if outcome == "ok":
            row["answered"] += 1
        elif outcome is None:
            row["never_answered"] += 1
        else:
            row["failed"] += 1
            errors[f"{row['step']} ({region})" if role in BY_REGION and region else row["step"], short(error)] += 1
    return sorted(counts.values(), key=lambda r: (-r["asked"], r["step"])), errors

def matching(data):
    """How a comparison's subjects were matched, in counts (the review of open items, 2026-11-17: what matching did on
    documents the owner can't share): subjects a source (A, B: the comparison's order) and joined across; links by
    band (links.SHOWN) and the family each one's evidence weighed most for (links.FAMILIES); sets of interchangeable
    units; subjects named only as a document's parts (align.generic, align.placeholder: "sheet", "revision 2"), and
    the links they're in; findings by relation. None without a merged index."""
    from .align import generic, placeholder
    from .links import FAMILIES, SHOWN
    index = data.get("index") or {}
    sources, subjects = index.get("sources") or [], index.get("subjects") or []
    if not sources or not subjects:
        return None
    letter = {source: chr(ord("A") + n) for n, source in enumerate(sources)}
    parts = {(next(iter(s["claims"])), s["name"]) for s in subjects
             if len(s["claims"]) == 1 and (generic(s["name"]) or placeholder(s["name"]))}
    found = {}
    for s in subjects:
        if len(s["claims"]) != 1:
            continue
        here = (next(iter(s["claims"])), s["name"])
        for link in s.get("links", []):
            found.setdefault(frozenset((here, (link["source"], link["other"]))), link)
    bands, families = Counter(), Counter()
    for link in found.values():
        p = link.get("probability")
        band = "plausible" if p is not None and p >= SHOWN["plausible"] else link.get("level", "possible")
        bands[band if band in SHOWN else "possible"] += 1
        weights = {k: v for k, v in (link.get("contributions") or {}).items() if v > 0}
        if weights:
            family = max(weights, key=lambda k: (weights[k], k))
            families[FAMILIES.get(family, family)] += 1
    return {"subjects": {letter[x]: sum(1 for s in subjects if x in s["claims"]) for x in sources},
            "joined": sum(1 for s in subjects if len(s["claims"]) > 1),
            "links": len(found), "bands": {b: bands[b] for b in SHOWN if bands[b]},
            "decided_by": dict(families.most_common()),
            "sets": len(index.get("sets") or []),
            "document_parts": len(parts),
            "document_part_links": sum(1 for pair in found if pair & parts),
            "findings": dict(Counter(f.get("relation", "") for f in data.get("findings") or []).most_common())}

def comparison(data):
    """The last comparison's counts: {created_at, mode, paused, coverage: {status: n}, reranker, embedding,
    matching}."""
    reranked = (data.get("retrieval") or {}).get("reranked") or None
    vectors = data.get("vectors") or None
    counts = ("model", "requests", "failed", "not_sent")
    return {"created_at": data.get("created_at", ""), "mode": data.get("mode", ""), "paused": data.get("paused") or "",
            "coverage": dict(Counter(r.get("status", "") for r in data.get("coverage") or []).most_common()),
            "reranker": {k: reranked[k] for k in counts if k in reranked} if reranked else None,
            "embedding": {k: vectors[k] for k in counts if k in vectors} if vectors else None,
            "matching": matching(data)}

def gather(folder, cache_path, settings, limit=10):
    """What `debug` prints, as data."""
    from . import __version__, fixtures
    from .store import Store, StoreError
    out = {"version": __version__, "python": platform.python_version(), "pymupdf": _pymupdf(),
           "store": str(folder), "cache": str(cache_path), "endpoint": endpoint(settings.model_dump()),
           "endpoint_of": "the store's settings",
           "environment": {name: bool(os.environ.get(name, "").strip()) for name in ("OPENAI_BASE_URL",
                                                                                      settings.model_key_env)},
           "steps": [], "comparison": None, "errors": [], "other_errors": 0}
    if not (folder / "store.sqlite").exists():
        return out
    with Store.open(folder) as store:
        roles = store.query_roles()
        try:
            data = store.comparison()
        except StoreError:
            data = None
    if data is not None:
        out["comparison"] = comparison(data)
        if data.get("settings"):
            out["endpoint"], out["endpoint_of"] = endpoint(data["settings"]), "the last comparison's"
    outcomes = {}
    if cache_path.exists():
        with fixtures.open(cache_path, "read") as cache:
            outcomes = cache.outcomes(roles)
    out["steps"], errors = steps(roles, outcomes)
    ranked = errors.most_common()
    out["errors"] = [{"step": step, "count": n, "error": error} for (step, error), n in ranked[:limit]]
    out["other_errors"] = sum(n for _, n in ranked[limit:])
    return out

def _pymupdf():
    try:
        import pymupdf
        return pymupdf.VersionBind
    except (ImportError, AttributeError):
        return ""

def matched_lines(m, n):
    """matching's counts as a few lines."""
    sides = ", ".join(f"{side} {n(count)}" for side, count in m["subjects"].items())
    out = [f"  subjects: {sides}; joined across the sources {n(m['joined'])}"]
    if m["links"]:
        bands = ", ".join(f"{band} {n(count)}" for band, count in m["bands"].items())
        out.append(f"  links (subjects possibly one, kept apart): {n(m['links'])} ({bands})")
        if m["decided_by"]:
            out.append("    weighed most by: " + ", ".join(f"{k} {n(v)}" for k, v in m["decided_by"].items()))
    if m["sets"]:
        out.append(f"  sets of interchangeable units linked: {n(m['sets'])}")
    if m["document_parts"]:
        out.append(f"  subjects named only as a document's parts (a sheet, \"revision 2\"): {n(m['document_parts'])}"
                   + (f", in {n(m['document_part_links'])} links" if m["document_part_links"] else ""))
    if m["findings"]:
        out.append("  claim pairs judged: " + ", ".join(f"{k or 'unstated'} {n(v)}" for k, v in m["findings"].items()))
    return out

def lines(found):
    """`debug`'s report, from gather's data."""
    def n(x):
        return f"{x:,}"
    point, env = found["endpoint"], found["environment"]
    out = [f"semantic-pdf-diff {found['version']} (Python {found['python']}"
           + (f", PyMuPDF {found['pymupdf']})" if found["pymupdf"] else ")"),
           f"store: {found['store']}", f"answers cache: {found['cache']}",
           ", ".join(f"{name} {'set' if env[name] else 'not set'}" for name in env),
           f"endpoint ({found['endpoint_of']}): {point['base_url']}",
           f"  model      {point['model'] or 'none set'}"]
    reranker, embedding = point["reranker"], point["embedding"]
    out.append(f"  reranker   {reranker['model']} ({reranker['api']} API) at {reranker['url']}" if reranker else
               "  reranker   none set")
    out.append(f"  embedding  {embedding['model']} at {embedding['url']} ("
               + (f"{embedding['dimensions']} dimensions asked)" if embedding["dimensions"] else "its own dimensions)")
               if embedding else "  embedding  none set")
    wide = max([len(r["step"]) for r in found["steps"]] + [len(e["step"]) for e in found["errors"]] + [12]) + 2
    if not found["steps"]:
        out.append("no requests asked yet" + ("" if found["comparison"] else " (no store, or no run in it)"))
    else:
        out.append("requests the store's runs asked, by step (never answered: not sent, as after sending stopped, a "
                   "cap or Ctrl+C; the next run asks again):")
        out.append(f"  {'step':<{wide}}{'asked':>9}{'answered':>10}{'failed':>8}{'never answered':>16}")
        out += [f"  {r['step']:<{wide}}{n(r['asked']):>9}{n(r['answered']):>10}{n(r['failed']):>8}"
                f"{n(r['never_answered']):>16}" for r in found["steps"]]
    last = found["comparison"]
    if last:
        out.append(f"the last comparison ({last['created_at'][:16].replace('T', ' ')}, {last['mode']}):")
        if last["paused"]:
            out.append(f"  paused: {last['paused']}")
        out.append("  coverage: " + (", ".join(f"{k} {n(v)}" for k, v in last["coverage"].items()) or "none"))
        for name in ("reranker", "embedding"):
            if last[name]:
                asked = last[name].get("requests", 0)
                unsent = last[name].get("not_sent", 0)
                out.append(f"  {name}: {n(asked)} request{'' if asked == 1 else 's'}, "
                           f"{n(last[name].get('failed', 0))} failed" + (f", {n(unsent)} not sent" if unsent else ""))
        found_matching = last.get("matching")
        if found_matching:
            out += matched_lines(found_matching, n)
    if found["errors"]:
        out.append("errors recorded, the most frequent first (a server's error may quote what was sent):")
        out += [f"  {e['step']:<{wide}}{n(e['count']):>7}  {e['error']}" for e in found["errors"]]
        if found["other_errors"]:
            out.append(f"  and {n(found['other_errors'])} more failures with other errors (--errors N shows more)")
    elif found["steps"]:
        out.append("no errors recorded")
    return out
