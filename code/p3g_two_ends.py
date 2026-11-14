#!/usr/bin/env python3
"""Topic 43 / P3G (POSTHOC_NOTE_P3G.md P2, P3, P9; POST HOC): paper-level numbers at both ends of the FP bounds, offline.

Upper end: a flag = an unresolved academic reference (full cascade), as in v1.4.
Lower end: a flag = an unresolved academic reference that the deep search found (F: confirmed to exist).
For the pooled corpus and the .bib branch (POSTHOC_NOTE P1-rule), both periods (2024-26 = hold-out):
  shares of papers with >= 1, 2, 3 flags (Wilson); k_emp at alpha 0.05 / 0.01 with the smallest k whose Wilson upper
  limit is <= alpha; FP bounds of the academic tier with paper-bootstrap CIs (B = 1000, seed 42, f_hi fixed);
  PPV ceiling pi / (pi + (1 - pi) u) at pi = 0.39% and 0.5% for u = upper and lower end;
  sensitivity of the lower end to f (P3).
Outputs: results/p3g_two_ends.csv (long), results/p3g_two_ends.json
Usage: python code/p3g_two_ends.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3f_bounds as fb  # noqa: E402
import p3g_branch_split as bs  # noqa: E402
from p1_theory_tables import ppv_star  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
A = ["J", "C", "P"]
PIS = {"0.39%": 0.0039, "0.5%": 0.005}
FS = [0.0, None, 0.05, 0.10, 0.214, 0.522]  # None = f_hi of D-splice (used); last = gen_a f_hi (rounded below from file)


def main():
    d = bs.base()
    gs = json.loads((RES / "p3f_gt3_summary.json").read_text(encoding="utf-8"))
    fm = gs["false_match"]
    f_hi = fm["f_hi_used"]
    f_gena = fm["gen_a"]["f_hi"]
    f_u = gs["cells"]["2019-21|A"]["F_over_U"]
    out = {"label": "POST HOC (POSTHOC_NOTE_P3G.md P2, P3, P9); offline; academic references; full cascade", "f_hi": f_hi}
    rows = []
    for scope in ("pooled", "bib"):
        dd = d if scope == "pooled" else d[d.paper_branch == "bib"]
        for per in ("2019-21", "2024-26"):
            g = dd[dd.period == per]
            for end, col in (("upper", "u"), ("lower", "f")):
                P = bs.paper_counts(g, col)
                sh, ke = bs.shares(P, 3), bs.k_emp(P)
                key = f"{scope}|{per}|{end}"
                out[key] = dict(papers=len(P), flags=sh, k_emp=ke)
                for k, v in sh.items():
                    rows.append(dict(scope=scope, period=per, end=end, what=f"share_ge{k}", value=v["share"], k=v["papers"],
                                     n=v["n"], lo=v["wilson"][0], hi=v["wilson"][1]))
                for a, v in ke.items():
                    rows.append(dict(scope=scope, period=per, end=end, what=f"k_emp_{a}", value=v["k_emp"],
                                     k_wilson=v["k_wilson_upper"], share=v["share_at_k"]))
        # bounds of the academic tier, 2019-21, and PPV ceilings
        g = dd[(dd.period == "2019-21") & dd.tier.isin(A)]
        c = fb.cell(g, f_hi, boot=True)
        out[f"{scope}|bounds"] = c
        ppv = {}
        for pn, pi in PIS.items():
            ppv[pn] = dict(upper_end=ppv_star(pi, c["fp_upper"]), lower_end=ppv_star(pi, c["fp_lower"]),
                           upper_end_ci=[ppv_star(pi, c["fp_upper_ci"][1]), ppv_star(pi, c["fp_upper_ci"][0])],
                           lower_end_ci=[ppv_star(pi, c["fp_lower_ci"][1]), ppv_star(pi, c["fp_lower_ci"][0])])
            rows.append(dict(scope=scope, period="2019-21", end="both", what=f"ppv_{pn}", value=ppv[pn]["upper_end"],
                             share=ppv[pn]["lower_end"]))
        out[f"{scope}|ppv"] = ppv
        sens = []
        for f in FS:
            fv = f_hi if f is None else (f_gena if f == 0.522 else (f_u if f == 0.214 else f))
            x = c["R"] / (1 - fv)
            lo = max(0.0, c["U"] - x) / c["N"]
            sens.append(dict(f=fv, label="D-splice f_hi" if f is None else ("gen_a f_hi" if f == 0.522 else ("F/U" if f == 0.214 else "")),
                             fp_lower=lo))
            rows.append(dict(scope=scope, period="2019-21", end="lower", what="sensitivity", value=lo, share=fv))
        out[f"{scope}|sensitivity"] = sens
    pd.DataFrame(rows).to_csv(RES / "p3g_two_ends.csv", index=False)
    (RES / "p3g_two_ends.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    for scope in ("pooled", "bib"):
        for per in ("2019-21", "2024-26"):
            for end in ("upper", "lower"):
                v = out[f"{scope}|{per}|{end}"]
                print(scope, per, end, {k: (x["papers"], round(x["share"] * 100, 1)) for k, x in v["flags"].items()},
                      {a: (x["k_emp"], x["k_wilson_upper"]) for a, x in v["k_emp"].items()})
        b = out[f"{scope}|bounds"]
        print(scope, "bounds", {k: b[k] for k in ("N", "U", "F", "R", "fp_lower", "fp_upper", "fp_lower_ci", "fp_upper_ci")})
        print(scope, "ppv", {k: (round(v["upper_end"] * 100, 1), round(v["lower_end"] * 100, 1)) for k, v in out[f"{scope}|ppv"].items()})
        print(scope, "sens", [(round(s["f"] * 100, 2), round(s["fp_lower"] * 100, 3)) for s in out[f"{scope}|sensitivity"]])


if __name__ == "__main__":
    main()
