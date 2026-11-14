#!/usr/bin/env python3
"""Topic 43 / P3E (PREREG_AMENDMENT_7 (a)): offline summary of the cascade completion for the paper and the report.

Reads P3E/cascade_targets.csv and P3E/cascade_passes.json (written by p3e_complete_cascade.py) and the stored answers
of cache_p3e/ (fetch dates only). Writes results/p3e_cascade_summary.json: passes (start, end, asked, completed, first
refusal per backend, requests), targets and still-unanswered counts by period x tier x state before, by missing
backend, the change of state of the targets, and the date range of the stored answers.
Usage: python code/p3e_cascade_summary.py
"""
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DER = Path(os.environ.get("THS_DATASETS", r"D:\Datasets")) / "_derived" / "43"


def main():
    t = pd.read_csv(ROOT / "P3E" / "cascade_targets.csv", dtype=str, keep_default_na=False)
    p = json.loads((ROOT / "P3E" / "cascade_passes.json").read_text(encoding="utf-8"))
    t["acad"] = t.tier.isin(["J", "C", "P"])
    t["left"] = t.missing_after != ""
    out = {"label": "cascade completion (Amendment 7 (a))", "n_targets": len(t),
           "passes": [{k: v for k, v in x.items() if k != "free_ram_gb"} for x in p["passes"]],
           "finished": "unanswered_after_last_pass" in p}
    g = t.groupby(["period", "tier", "state_before"]).agg(n=("ref_id", "size"), left=("left", "sum")).reset_index()
    out["by_period_tier_state"] = g.to_dict("records")
    for per in ("2019-21", "2024-26"):
        a = t[(t.period == per) & t.acad]
        out[f"academic_{per}"] = {"targets": int(len(a)), "unresolved_before": int((a.state_before == "unresolved").sum()),
                                  "unresolved_left": int(((a.state_before == "unresolved") & a.left).sum()),
                                  "resolved_by_completion": int(((a.state_before == "unresolved") &
                                                                 (a.state_after == "resolved")).sum()),
                                  "left_any": int(a.left.sum())}
    miss = {}
    for b in ("openalex", "s2", "dblp"):
        m = t.missing.str.contains(b)
        miss[b] = {"before": int(m.sum()), "left": int((t.missing_after.str.contains(b)).sum())}
    out["by_backend"] = miss
    out["state_change"] = t.groupby(["state_before", "state_after"]).size().reset_index().values.tolist()
    dates = []
    for f in (DER / "cache_p3e").rglob("*.json"):
        try:
            dates.append(json.loads(f.read_text(encoding="utf-8")).get("fetched", "")[:10])
        except (ValueError, OSError):
            pass
    out["cache_p3e_fetched"] = [min(dates), max(dates)] if dates else []
    out["cache_last_date"] = max(dates) if dates else p["passes"][-1]["end"][:10]
    (ROOT / "results" / "p3e_cascade_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "by_period_tier_state"}, indent=1))


if __name__ == "__main__":
    main()
