#!/usr/bin/env python3
"""Topic 43 / P1: tests of H1 and H2 (PREREG_43.md §5) per cumulative backend column.

H1  u_A (def 1, 2019-21) in [0.5 %, 5 %]; PASS = point estimate in the window, strong = whole paper-bootstrap CI.
H2  u_W >= 5 u_A (def 1, 2019-21); PASS = point ratio >= 5, strong = lower bound of the paper-bootstrap ratio CI >= 5.
The preregistered test uses the final cascade state (column s2 = +S2). Crossref-only and +DBLP are reported as
secondary columns (backend table, PREREG_AMENDMENT_3). A reference is unresolved in column c if no backend up to c
resolved it; the denominator is the final resolved/unresolved set (rate-limited and no-title excluded).
Input:  $THS_DATASETS/_derived/43/p1_groundtruth_refs_full.csv
Output: results/p1_hypotheses_h1h2.json
Usage:  python p1_hypotheses.py --seed 42 [--boot 1000] [--interim]
        --interim: input _derived/43/interim/, output results/interim/; the +S2 column is reported as provisional
        (s2_pending refs count as unresolved) and labelled so.
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
from p1_backend_table import COLS, first_hit_stage  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--interim", action="store_true")
    args = ap.parse_args()
    der, out_dir = (DERIVED / "interim", ROOT / "results" / "interim") if args.interim else (DERIVED, ROOT / "results")
    d = pd.read_csv(der / "p1_groundtruth_refs_full.csv", dtype={"arxiv_id": str, "key": str}, low_memory=False)
    d = d[(d.period == "2019-21") & d.def1_status.isin(["resolved", "unresolved"])].copy()
    d["stage"] = np.where(d.def1_status == "resolved", d.backends_hit.map(first_hit_stage), len(COLS))
    papers = sorted(d.arxiv_id.unique())
    rng = np.random.default_rng(args.seed)
    idx = rng.integers(0, len(papers), (args.boot, len(papers)))
    out = {"seed": args.seed, "boot": args.boot, "period": "2019-21", "definition": "def 1", "columns": {}}
    for c in ["crossref", "dblp", "s2"]:
        x = (d.stage > COLS.index(c)).astype(int)
        agg = {}
        for name, mask in (("A", d.tier.isin(ACADEMIC)), ("W", d.tier == "W")):
            g = pd.DataFrame({"p": d.arxiv_id[mask], "x": x[mask]}).groupby("p").x.agg(["sum", "count"])
            agg[name] = g.reindex(papers).fillna(0)
        kA, nA = int(agg["A"]["sum"].sum()), int(agg["A"]["count"].sum())
        kW, nW = int(agg["W"]["sum"].sum()), int(agg["W"]["count"].sum())
        uA, uW = kA / nA, kW / nW
        bA = agg["A"]["sum"].values[idx].sum(1) / np.maximum(agg["A"]["count"].values[idx].sum(1), 1)
        bW = agg["W"]["sum"].values[idx].sum(1) / np.maximum(agg["W"]["count"].values[idx].sum(1), 1)
        ciA = [float(v) for v in np.quantile(bA, [0.025, 0.975])]
        ratio = np.where(bA > 0, bW / np.where(bA > 0, bA, 1), np.inf)
        ciR = [float(v) for v in np.quantile(ratio, [0.025, 0.975])]
        lab = {"crossref": "Crossref-only", "dblp": "+DBLP", "s2": "+S2 (final cascade state)"}[c]
        if args.interim and c == "s2":
            lab = f"+S2 PROVISIONAL (chưa hoàn tất, n_pending={int((d.get('s2_pending', 0) == 1).sum())})"
        out["columns"][c] = {
            "label": lab, "primary": c == "s2" and not args.interim,
            "H1": {"k": kA, "n": nA, "n_papers": len(papers), "u_A": uA, "paper_bootstrap95": ciA,
                   "wilson95": list(wilson(kA, nA)), "PASS": bool(0.005 <= uA <= 0.05),
                   "strong": bool(0.005 <= ciA[0] and ciA[1] <= 0.05)},
            "H2": {"k_W": kW, "n_W": nW, "u_W": uW, "u_A": uA, "ratio": uW / uA if uA else None,
                   "ratio_paper_bootstrap95": ciR, "PASS": bool(uA and uW / uA >= 5), "strong": bool(ciR[0] >= 5)}}
    if args.interim:
        out.update(interim=True, s2_pending=int((d.get("s2_pending", 0) == 1).sum()),
                   interim_note="INTERIM: Crossref-only and +DBLP exact; +S2 provisional")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "p1_hypotheses_h1h2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for c, v in out["columns"].items():
        h1, h2 = v["H1"], v["H2"]
        print(f"{v['label']}: H1 u_A={h1['u_A']:.4f} ({h1['k']}/{h1['n']}, {h1['n_papers']} papers) "
              f"CI {h1['paper_bootstrap95'][0]:.4f}-{h1['paper_bootstrap95'][1]:.4f} PASS={h1['PASS']} "
              f"strong={h1['strong']} | H2 ratio={h2['ratio']:.2f} CI {h2['ratio_paper_bootstrap95'][0]:.2f}-"
              f"{h2['ratio_paper_bootstrap95'][1]:.2f} PASS={h2['PASS']} strong={h2['strong']}")


if __name__ == "__main__":
    main()
