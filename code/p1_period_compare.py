#!/usr/bin/env python3
"""Topic 43 / P1 (EXPLORATORY, not preregistered): u_acad of 2019-21 vs 2024-26 citing papers on the same backend.

Question: is the legitimate-reference baseline stable across the LLM period? For each cumulative backend column
(cascade order of PREREG_AMENDMENT_3) the two periods are compared on tier A = J+C+P, def 1, same denominator rule as
p1_backend_table.py (rate-limited after the retry rounds and no-title excluded). The two periods are disjoint paper
sets, so each is resampled on its own (paper-level bootstrap, B = 1000) and the difference / ratio is taken per draw.
Input:  $THS_DATASETS/_derived/43/p1_groundtruth_refs_full.csv
Output: results/p1_period_compare.{csv,json}
Usage:  python p1_period_compare.py --seed 42 [--boot 1000]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import wilson  # noqa: E402
from ground_truth_p1 import ACADEMIC, DERIVED, ROOT  # noqa: E402
from p1_backend_table import COLS, LABEL, first_hit_stage  # noqa: E402


def paper_draws(g, j, rng, B):
    """Per-paper (k, n) at backend column j, then B paper-level bootstrap draws of k/n."""
    x = (g.stage > j).astype(int)
    a = pd.DataFrame({"p": g.arxiv_id.values, "x": x.values}).groupby("p").x.agg(["sum", "count"])
    idx = rng.integers(0, len(a), (B, len(a)))
    return int(x.sum()), len(x), len(a), a["sum"].values[idx].sum(1) / a["count"].values[idx].sum(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    src = DERIVED / "p1_groundtruth_refs_full.csv"
    d = pd.read_csv(src, dtype={"arxiv_id": str, "key": str}, low_memory=False)
    d = d[d.tier.isin(ACADEMIC) & d.def1_status.isin(["resolved", "unresolved"])].copy()
    d["stage"] = np.where(d.def1_status == "resolved", d.backends_hit.map(first_hit_stage), len(COLS))
    rng = np.random.default_rng(args.seed)
    rows = []
    for j, c in enumerate(COLS):
        r = {"column": LABEL[c]}
        draws = {}
        for per in ("2019-21", "2024-26"):
            k, n, npap, v = paper_draws(d[d.period == per], j, rng, args.boot)
            lo, hi = wilson(k, n)
            draws[per] = v
            r.update({f"k_{per}": k, f"n_{per}": n, f"papers_{per}": npap, f"u_{per}": round(k / n, 5),
                      f"boot_{per}": f"{np.quantile(v, .025):.4f}-{np.quantile(v, .975):.4f}",
                      f"wilson_{per}": f"{lo:.4f}-{hi:.4f}"})
        diff = draws["2024-26"] - draws["2019-21"]
        ratio = draws["2024-26"] / draws["2019-21"]
        r.update({"diff_pp": round(100 * (r["u_2024-26"] - r["u_2019-21"]), 3),
                  "diff_boot_pp": f"{100 * np.quantile(diff, .025):.3f}..{100 * np.quantile(diff, .975):.3f}",
                  "ratio": round(r["u_2024-26"] / r["u_2019-21"], 3),
                  "ratio_boot": f"{np.quantile(ratio, .025):.3f}-{np.quantile(ratio, .975):.3f}",
                  "ci_diff_covers_0": bool(np.quantile(diff, .025) <= 0 <= np.quantile(diff, .975))})
        rows.append(r)
    tab = pd.DataFrame(rows)
    tab.insert(0, "interim", False)
    out = ROOT / "results"
    tab.to_csv(out / "p1_period_compare.csv", index=False)
    meta = {"interim": False, "exploratory": True, "seed": args.seed, "boot": args.boot, "input": str(src),
            "spec": "tier A (J+C+P), def 1, cumulative cascade columns; periods resampled independently by paper",
            "rows": rows}
    (out / "p1_period_compare.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(tab.drop(columns=["interim"]).to_string(index=False))


if __name__ == "__main__":
    main()
