"""Re-key judge caches into each folder's replay fixture, by rebuilding their requests.

A `.judge-cache` (or `.postmortem-cache`) file is named by the hash of the whole request body
(the model and endpoint, the prompt, the images, the answer schema). For every request a folder
makes today, under each judge it had and each answer schema the code has had (from git), this
computes that old name; a file found under it is an answer to exactly the query rebuilt now, and is
recorded in the folder's fixture under the query's hash. Files no rebuilt request names are
stale and let go (the owner: "Let go of stale answers that don't have an obvious transition via
replay"). Temporary, like --rekey-from: removed once nothing needs re-keying.

    set -a; . ./.env; set +a      # the endpoint URL is part of the old names; nothing is sent
    python scripts/rekey_judge_caches.py benchmarks/rounds/*/pairs-* benchmarks/spotchecks/* benchmarks/batches/*
"""
import argparse
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
CACHES = (".judge-cache", ".postmortem-cache")


def schemas(name):
    """Each distinct JSON schema class `name` in models.py has had, newest first."""
    commits = subprocess.run(["git", "log", "--format=%h", "--", "src/semantic_pdf_diff/models.py"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    seen, out = set(), []
    with tempfile.TemporaryDirectory() as d:
        for c in commits:
            source = subprocess.run(["git", "show", f"{c}:src/semantic_pdf_diff/models.py"], cwd=ROOT,
                                    capture_output=True, text=True).stdout
            if f"class {name}(" not in source:
                continue
            package = Path(d) / c / "semantic_pdf_diff"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("")
            (package / "models.py").write_text(source)
            saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("semantic_pdf_diff")}
            sys.path.insert(0, str(package.parent))
            try:
                schema = json.dumps(getattr(importlib.import_module("semantic_pdf_diff.models"), name).model_json_schema(),
                                    sort_keys=True)
            except Exception:
                schema = None
            finally:
                sys.path.pop(0)
                for k in [k for k in sys.modules if k.startswith("semantic_pdf_diff")]:
                    del sys.modules[k]
                sys.modules.update(saved)
            if schema and schema not in seen:
                seen.add(schema)
                out.append(json.loads(schema))
    return out

def posing(schema_class, schema):
    """A stand-in for a schema class with an older JSON schema (only the old name uses it)."""
    return type(schema_class.__name__, (), {"model_json_schema": staticmethod(lambda: schema)})

def reviewers(folder, *subfolders):
    names = set()
    for sub in subfolders:
        for d in folder.glob(sub):
            for f in d.glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                names.add(data.get("reviewer"))
    return names - {None}

def requests(folder):
    """[(models, schema class, prompt, images, key)] every request the folder makes today."""
    from semantic_pdf_diff import review, rounds
    from semantic_pdf_diff.models import PairVerdict, PanelLabel, PanelQuestionLabel
    from semantic_pdf_diff.postmortem import ANALYST, Reading
    out = []
    if (folder / "pairs.json").exists():
        batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
        spec = folder.parent / "round.json"
        by_dir = {}
        if spec.exists():  # a round's batch: one rubric
            round_ = json.loads(spec.read_text())
            models = reviewers(folder, "verdicts*") | set(round_.get("judges", [])) | set(round_.get("escalate", [])) \
                | set(round_.get("confirm_judges", []))
            by_dir[round_.get("rubric", "v1")] = models
        else:  # a spot check: verdicts/ under v4, verdicts-<rubric>/ under that rubric
            for d in folder.glob("verdicts*"):
                rubric = "v4" if d.name == "verdicts" else d.name.split("-", 1)[1]
                by_dir.setdefault(rubric, set()).update(reviewers(folder, d.name))
        for rubric, models in by_dir.items():
            try:
                for item, order, prompt, images, *_ in rounds.pair_requests(folder, batch, rubric):
                    out.append((models, PairVerdict, prompt, images, ("judge", item["id"], rubric, order)))
            except (ValueError, KeyError) as e:
                print(f"  {folder}: rubric {rubric} can't be rebuilt ({e})")
        pm = folder / "postmortem.json"
        if pm.exists():
            evidence = json.loads(pm.read_text(encoding="utf-8"))
            analyst = {"google/gemini-3.1-pro"}
            text = json.dumps({k: evidence.get(k) for k in ("described", "decision", "overall", "partitions", "samples")},
                              ensure_ascii=False, indent=1)
            out.append((analyst, Reading, ANALYST.format(evidence=text), [], ("postmortem", evidence.get("batch") or "")))
    if (folder / "batch.json").exists():  # a review batch: answers and questions
        batch = json.loads((folder / "batch.json").read_text(encoding="utf-8"))
        answers, questions = reviewers(folder, "labels"), reviewers(folder, "question-labels")
        for item in review.public_items(batch):
            out.append((answers, PanelLabel, review.judge_prompt(item), [folder / i["src"] for i in item["images"]],
                        ("review", item["id"], "answers")))
        for item in review.question_items(batch):
            out.append((questions, PanelQuestionLabel, review.question_prompt(item),
                        [folder / i["src"] for i in item["request"]["images"]], ("review", item["id"], "questions")))
    return out

def dates(folder):
    """{file name: the date git first recorded it}, for answers' `recorded` dates."""
    log = subprocess.run(["git", "log", "--reverse", "--format=@%cs", "--name-only", "--", str(folder)], cwd=ROOT,
                         capture_output=True, text=True).stdout
    found, date = {}, None
    for line in log.splitlines():
        if line.startswith("@"):
            date = line[1:]
        elif line.strip():
            found.setdefault(Path(line).name, date)
    return found

def rekey(folder, candidates):
    from datetime import datetime, timezone
    from semantic_pdf_diff import fixtures
    from semantic_pdf_diff.llm import Client
    from semantic_pdf_diff.models import EVALUATOR_SETTINGS, Settings
    files = {p.stem: p for c in CACHES for p in (folder / c).glob("*.json")}
    if not files:
        return None
    known = dates(folder)
    carried, invalid = set(), 0
    fixture = fixtures.folder_fixture(folder)
    try:
        for models, schema, prompt, images, key in requests(folder):
            if not all(Path(i).exists() for i in images):
                continue
            for model in sorted(models):
                client = Client(Settings.from_env(model=model, **EVALUATOR_SETTINGS), None)
                for old in candidates[schema.__name__]:
                    request = client.prepare(prompt, posing(schema, old), images, key)
                    path = files.get(request.request_hash)
                    if path is None:
                        continue
                    answer = path.read_text(encoding="utf-8")
                    try:
                        schema.model_validate_json(answer)
                    except ValueError:
                        invalid += 1
                        break
                    today = client.prepare(prompt, schema, images, key)
                    recorded = known.get(path.name) or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
                    fixture.record(today.query, model, 0, outcome="ok", answer=answer, recorded=recorded,
                                   description=today.description, recipe=key)
                    carried.add(path.stem)
                    break
    finally:
        fixture.close()
    return {"files": len(files), "carried": len(carried), "invalid": invalid, "let go": len(files) - len(carried)}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folders", type=Path, nargs="+")
    args = parser.parse_args(argv)
    from semantic_pdf_diff import models, postmortem
    candidates = {}
    for name in ("PairVerdict", "PanelLabel", "PanelQuestionLabel", "Reading"):
        today = getattr(models, name, None) or getattr(postmortem, name)
        found = [today.model_json_schema()] + schemas(name)
        candidates[name] = [json.loads(s) for s in dict.fromkeys(json.dumps(f, sort_keys=True) for f in found)]
    print("answer schemas from git:", {k: len(v) for k, v in candidates.items()})
    total = {}
    for folder in args.folders:
        result = rekey(folder, candidates)
        if result is not None:
            print(f"{folder}: {result}")
            for k, v in result.items():
                total[k] = total.get(k, 0) + v
    print("total:", total)

if __name__ == "__main__":
    main()
