"""Check the reading planner against the page tests: for each model and kind of sheet, the plan its profile picks,
what that plan measured, and the cheapest tested plan that read every font size at 90%.

    python scripts/check_profiles.py      # offline: reads benchmarks/eyetest and benchmarks/pagetest results

Every figure comes from the stored results (docs/research/page-tests-2026-10-01.md quotes this output).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
EYES = ROOT / "benchmarks/eyetest/results.json"
PAGES = ROOT / "benchmarks/pagetest/results.json"

def name(side, px):
    return f"{'whole' if side is None else f't{side}'}-{px}"

def main():
    from semantic_pdf_diff_lab.bench import pagetest, profiles
    pages = json.loads(PAGES.read_text(encoding="utf-8"))["models"]
    for model, measured in pages.items():
        profile = profiles.load(model, EYES, PAGES)
        if profile is None:
            print(f"{model}: no eye test")
            continue
        print(f"\n{model}: calibration {profile.calibration} from {profile.plans_measured} plans; "
              f"ceiling {profile.ceiling_px} px")
        for kind, parts in measured["pooled"].items():
            tested = parts.get("static", {})
            if not tested:
                continue
            w, h = pagetest.PAGES[pagetest.paper(kind)]
            fonts = pagetest.fonts(kind)
            sides = tuple(sorted({profiles._plan_of(n)[0] for n in tested}, key=lambda s: (s is not None, -(s or 0))))
            renders = tuple(sorted({profiles._plan_of(n)[1] for n in tested}))
            chosen = profiles.plan(profile, w, h, min(fonts), max(fonts), sides=sides, renders=renders)
            picked = None if chosen is None else name(chosen["side"], chosen["px"])
            reads_all = lambda r: all(v >= 0.9 for v in r["by_pt"].values())
            cheapest = min(((r["queries"], profiles._plan_of(n)[1], n) for n, r in tested.items() if reads_all(r)),
                           default=None)
            got = tested.get(picked, {})
            print(f"  {kind:14s} fonts {min(fonts):g}-{max(fonts):g} pt | planned {picked} "
                  f"({chosen and chosen['tiles']} tiles, predicted {chosen and chosen['predicted_pt']} pt): "
                  f"measured recall {got.get('recall')} | cheapest reading every size: "
                  f"{cheapest[2] if cheapest else None} ({cheapest[0] if cheapest else '-'} tiles)")

if __name__ == "__main__":
    main()
